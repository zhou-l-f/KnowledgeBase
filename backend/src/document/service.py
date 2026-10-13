"""文档管理服务层：文件上传 -> 多类型解析 -> 数据库存储 -> 向量化入库。

职责边界（与 agent 模块分工）：
- 数据库（SQLite）是文档唯一真源：知识库、文档、问答对三级结构；
- 上传的 .txt/.md 文件按 Q:/A: 格式解析为统一问答对，一个问答对 = 一条记录 = 一个向量索引单元；
- 每个知识库对应一个独立 Chroma 集合，集合名由知识库名哈希映射（Chroma 仅允许 ASCII）；
- 启动时不整体重建向量库，仅做一致性自检：结构标记缺失或数量不一致（含旧版索引）
  的集合才从数据库重建；
- 文档数据统一通过上传接口写入数据库（数据库为唯一数据源），不再读取 docs/ 磁盘目录；
- 媒体附件（图片等）以文件形式落盘、数据库存元数据与相对路径，不参与向量化，
  仅作为问答的佐证材料随 invoke 答案返回展示；
- agent 模块仅通过 get_store / list_kb_names / list_media_by_qa_ids 获取检索能力，
  见 src/agent/service.py。

向量写入失败只影响索引、不破坏数据库真源，下次启动的一致性自检会从数据库补齐。
"""

import hashlib
import mimetypes
import shutil
import sqlite3
import threading
import time
import uuid
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

from src.database import get_connection
from src.document.config import document_settings
from src.document.constants import (
    INDEX_SCHEMA,
    INDEX_SCHEMA_META_KEY,
    MAX_MEDIA_SIZE_BYTES,
    MEDIA_SUFFIXES,
    SUPPORTED_SUFFIXES,
)
from src.document.exceptions import (
    DocumentNotFoundError,
    KnowledgeBaseNotFoundError,
    MediaNotFoundError,
    QaItemNotFoundError,
)
from src.document.utils import decode_text, parse_qa_text

# 可重入锁：获取 embeddings / chroma client / store 时存在嵌套加锁，普通 Lock 会自死锁
_lock = threading.RLock()
_embeddings: HuggingFaceEmbeddings | None = None
_chroma_client = None
# 知识库名 -> 检索实例；启动自检后与数据库保持一致
_stores: dict[str, Chroma] = {}


def _log(message: str) -> None:
    """启动进度日志：必须 flush，否则 stdout 被重定向时会全缓冲，导致进度长时间不可见。"""
    print(f"[document] {message}", flush=True)


# ---------------------------------------------------------------------------
# 启动初始化：建表 -> 向量集合自检
# ---------------------------------------------------------------------------


def init() -> None:
    """启动初始化：建表、向量集合一致性自检。"""
    started = time.perf_counter()
    _log("文档模块初始化开始（数据库建表 + 向量库自检）")
    _init_db()
    _sync_stores()
    _remove_orphan_index_dirs()  # 收尾清理删除集合遗留的索引目录（被占用的留待下次启动清理）
    _remove_orphan_media_files()  # 收尾清理已无记录的媒体文件（被占用的留待下次启动清理）
    kbs = list_kbs()
    summary = ", ".join(f"{kb['name']}={kb['qa_count']}个问答" for kb in kbs) or "无"
    _log(f"文档模块初始化完成，共 {len(kbs)} 个知识库（{summary}），耗时 {time.perf_counter() - started:.1f}s")


def _init_db() -> None:
    """创建知识库 / 文档 / 问答对三张表（幂等）。"""
    with get_connection() as con:
        con.executescript(
            """
            create table if not exists knowledge_bases (
                id integer primary key autoincrement,
                name text not null unique,
                description text not null default '',
                created_at text not null default (datetime('now', 'localtime')),
                updated_at text not null default (datetime('now', 'localtime'))
            );
            create table if not exists documents (
                id integer primary key autoincrement,
                kb_id integer not null references knowledge_bases(id) on delete cascade,
                name text not null,
                created_at text not null default (datetime('now', 'localtime')),
                updated_at text not null default (datetime('now', 'localtime')),
                unique (kb_id, name)
            );
            create table if not exists qa_items (
                id integer primary key autoincrement,
                document_id integer not null references documents(id) on delete cascade,
                question text not null,
                answer text not null,
                seq integer not null,
                unique (document_id, seq)
            );
            create table if not exists media_assets (
                id integer primary key autoincrement,
                qa_id integer not null references qa_items(id) on delete cascade,
                filename text not null,
                stored_path text not null unique,
                mime_type text not null default 'application/octet-stream',
                size integer not null,
                created_at text not null default (datetime('now', 'localtime'))
            );
            """
        )


def _sync_stores() -> None:
    """为每个知识库准备检索实例；集合结构标记缺失或问答数量与数据库不一致时从数据库重建。"""
    kb_names = list_kb_names()
    for name in kb_names:
        if not _collection_synced(name, _count_qas(name)):
            _log(f"向量集合「{name}」与数据库不一致（旧版结构或缺向量），从数据库重建…")
            _rebuild_kb_from_db(name)
    for key in [k for k in _stores if k not in set(kb_names)]:
        _stores.pop(key)


def _collection_synced(kb_name: str, db_qa_count: int) -> bool:
    """集合与数据库是否一致：存在、带结构版本标记、问答数量相等。"""
    try:
        col = _get_chroma_client().get_collection(_collection_name(kb_name))
    except Exception:
        return False
    if (col.metadata or {}).get(INDEX_SCHEMA_META_KEY) != INDEX_SCHEMA:
        return False
    try:
        return col.count() == db_qa_count
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 懒加载单例：embeddings / chroma client / 各知识库检索实例
# ---------------------------------------------------------------------------


def _get_embeddings() -> HuggingFaceEmbeddings:
    global _embeddings
    if _embeddings is None:
        with _lock:
            if _embeddings is None:
                model = document_settings.embedding_model
                _log(f"正在加载向量化模型 {model}（首次加载较慢，请耐心等待）…")
                started = time.perf_counter()
                _embeddings = HuggingFaceEmbeddings(model_name=model)
                _log(f"向量化模型加载完成，耗时 {time.perf_counter() - started:.1f}s")
    return _embeddings


def _get_chroma_client():
    """底层 Chroma 客户端：用于集合的增删与元数据管理，检索走 _get_store。"""
    global _chroma_client
    if _chroma_client is None:
        with _lock:
            if _chroma_client is None:
                _chroma_client = chromadb.PersistentClient(
                    path=str(document_settings.chroma_dir),
                    settings=ChromaSettings(anonymized_telemetry=False),
                )
    return _chroma_client


def _collection_name(kb_name: str) -> str:
    """把知识库名映射为 Chroma 允许的 ASCII 集合名（仅允许 [a-zA-Z0-9._-]，3-512 字符）。"""
    return "kb_" + hashlib.md5(kb_name.encode("utf-8")).hexdigest()[:12]


def _get_store(kb_name: str) -> Chroma:
    """获取指定知识库的检索实例（含 embeddings），不存在则创建空集合。"""
    if not _stores.get(kb_name):
        with _lock:
            if not _stores.get(kb_name):
                _stores[kb_name] = Chroma(
                    collection_name=_collection_name(kb_name),
                    embedding_function=_get_embeddings(),
                    persist_directory=str(document_settings.chroma_dir),
                    # 关闭匿名遥测：默认会向 PostHog 上报，国内网络下会拖慢操作
                    client_settings=ChromaSettings(anonymized_telemetry=False),
                )
    return _stores[kb_name]


def get_store(kb_name: str) -> Chroma:
    """供 agent 模块获取检索实例：按知识库名返回向量集合。"""
    return _get_store(kb_name)


def _mark_synced(kb_name: str) -> None:
    """给集合打上结构版本标记，表明其内容与数据库一致（供下次启动自检跳过）。"""
    _get_chroma_client().get_collection(_collection_name(kb_name)).modify(
        metadata={INDEX_SCHEMA_META_KEY: INDEX_SCHEMA}
    )


def _drop_collection(kb_name: str) -> None:
    """删除知识库对应的集合（存在才删）并清掉内存缓存。

    不在删除后立即清理磁盘索引目录：Windows 下刚被加载过的集合文件可能仍被
    Chroma 进程占用，遗留目录统一在启动自检收尾时清理（见 _remove_orphan_index_dirs）。
    """
    client = _get_chroma_client()
    _stores.pop(kb_name, None)
    mapped = _collection_name(kb_name)
    if any(getattr(c, "name", str(c)) == mapped for c in client.list_collections()):
        client.delete_collection(mapped)


def _remove_orphan_index_dirs() -> None:
    """删除集合后磁盘上的 HNSW 索引目录会残留，清理 sqlite 中已无 segment 的目录。

    启动自检收尾时调用：个别目录可能仍被本进程内的 Chroma 句柄占用（Windows 文件锁），
    跳过并留待下次启动（新进程无句柄）继续清理。
    """
    db = document_settings.chroma_dir / "chroma.sqlite3"
    if not db.exists():
        return
    con = sqlite3.connect(db)
    try:
        active = {row[0] for row in con.execute("select id from segments")}
    finally:
        con.close()
    removed = []
    for path in sorted(document_settings.chroma_dir.iterdir()):
        if path.is_dir() and path.name not in active:
            try:
                shutil.rmtree(path)
                removed.append(path.name)
            except OSError as exc:
                _log(f"残留索引目录 {path.name} 暂被占用未清理（{exc}），下次启动继续清理")
    if removed:
        _log(f"清理 {len(removed)} 个残留索引目录：{removed}")


# ---------------------------------------------------------------------------
# 向量化：数据库问答记录 <-> Chroma 索引单元（向量 id = 问答记录主键，可精确删除/更新）
# ---------------------------------------------------------------------------


def _to_vector_doc(kb_name: str, row: dict) -> Document:
    """把一条问答记录转换为向量索引单元。"""
    return Document(
        page_content=f"Q: {row['question']}\nA: {row['answer']}",
        metadata={"source": row["doc_name"], "category": kb_name, "qa_id": row["id"]},
    )


def _rebuild_kb_from_db(kb_name: str) -> None:
    """删除旧集合并从数据库重建该知识库的全部向量（数据库为唯一真源）。"""
    with get_connection() as con:
        rows = con.execute(
            """
            select qi.id, qi.question, qi.answer, d.name as doc_name
            from qa_items qi
            join documents d on d.id = qi.document_id
            join knowledge_bases k on k.id = d.kb_id
            where k.name = ?
            order by qi.id
            """,
            (kb_name,),
        ).fetchall()
    _drop_collection(kb_name)
    store = _get_store(kb_name)
    if rows:
        store.add_documents(
            [_to_vector_doc(kb_name, dict(r)) for r in rows], ids=[str(r["id"]) for r in rows]
        )
    _mark_synced(kb_name)


# ---------------------------------------------------------------------------
# 知识库 CRUD
# ---------------------------------------------------------------------------


def create_kb(name: str, description: str = "") -> dict:
    """创建知识库并预热其空向量集合。"""
    kb_id = _insert_kb(name, description)
    kb_name = name.strip()
    _drop_collection(kb_name)  # 清理可能的同名遗留集合，避免复用旧索引
    _get_store(kb_name)
    _mark_synced(kb_name)
    return {"id": kb_id, "name": kb_name, "description": description, "qa_count": 0}


def _insert_kb(name: str, description: str = "") -> int:
    """仅向数据库插入知识库记录，返回主键（迁移导入使用，不涉及向量库）。"""
    name = name.strip()
    if not name:
        raise ValueError("知识库名称不能为空")
    with get_connection() as con:
        try:
            cur = con.execute(
                "insert into knowledge_bases (name, description) values (?, ?)", (name, description)
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"知识库 {name!r} 已存在") from exc
        return cur.lastrowid


def list_kbs() -> list[dict]:
    """列出全部知识库（含问答总数）。"""
    with get_connection() as con:
        rows = con.execute(
            """
            select k.id, k.name, k.description,
                   (select count(*) from qa_items qi
                    join documents d on d.id = qi.document_id
                    where d.kb_id = k.id) as qa_count
            from knowledge_bases k
            order by k.id
            """
        ).fetchall()
    return [dict(r) for r in rows]


def list_kb_names() -> list[str]:
    """列出全部知识库名（供 agent 模块做知识库选择）。"""
    with get_connection() as con:
        rows = con.execute("select name from knowledge_bases order by id").fetchall()
    return [r["name"] for r in rows]


def delete_kb(kb_name: str) -> None:
    """删除知识库：数据库记录（级联删除文档、问答与媒体记录）、向量集合与媒体文件一并删除。"""
    with get_connection() as con:
        qa_rows = con.execute(
            """
            select qi.id
            from qa_items qi
            join documents d on d.id = qi.document_id
            join knowledge_bases k on k.id = d.kb_id
            where k.name = ?
            """,
            (kb_name,),
        ).fetchall()
        cur = con.execute("delete from knowledge_bases where name = ?", (kb_name,))
        if cur.rowcount == 0:
            raise KnowledgeBaseNotFoundError(f"知识库 {kb_name!r} 不存在")
    _drop_collection(kb_name)
    _remove_media_files(_media_paths_of_qa_ids([r["id"] for r in qa_rows]))


def update_kb(kb_name: str, name: str | None = None, description: str | None = None) -> dict:
    """修改知识库：改描述仅落库；改名会按新名称重建向量集合（集合名由名称哈希映射）。"""
    if name is None and description is None:
        raise ValueError("未提供任何修改内容（name / description 至少填一项）")
    new_name = name.strip() if name is not None else None
    if name is not None and not new_name:
        raise ValueError("知识库名称不能为空")
    with get_connection() as con:
        row = con.execute("select id from knowledge_bases where name = ?", (kb_name,)).fetchone()
        if row is None:
            raise KnowledgeBaseNotFoundError(f"知识库 {kb_name!r} 不存在")
        if new_name is not None and new_name != kb_name:
            try:
                con.execute(
                    "update knowledge_bases set name = ?, updated_at = datetime('now', 'localtime') where id = ?",
                    (new_name, row["id"]),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"知识库 {new_name!r} 已存在") from exc
        if description is not None:
            con.execute(
                "update knowledge_bases set description = ?, updated_at = datetime('now', 'localtime') where id = ?",
                (description, row["id"]),
            )
        merged = con.execute(
            """
            select k.id, k.name, k.description,
                   (select count(*) from qa_items qi
                    join documents d on d.id = qi.document_id
                    where d.kb_id = k.id) as qa_count
            from knowledge_bases k
            where k.id = ?
            """,
            (row["id"],),
        ).fetchone()
    if new_name is not None and new_name != kb_name:
        # 旧集合名失效：清掉旧集合，按新名称从数据库重建
        _drop_collection(kb_name)
        _rebuild_kb_from_db(new_name)
    return dict(merged)


def _require_kb_id(kb_name: str) -> int:
    with get_connection() as con:
        row = con.execute("select id from knowledge_bases where name = ?", (kb_name,)).fetchone()
    if row is None:
        raise KnowledgeBaseNotFoundError(f"知识库 {kb_name!r} 不存在")
    return row["id"]


# ---------------------------------------------------------------------------
# 文档上传 / 查询 / 删除
# ---------------------------------------------------------------------------


def save_upload(kb_name: str, filename: str, content: bytes) -> dict:
    """解析上传文件并覆盖式入库（同名文档先删旧记录与旧向量），返回入库结果。"""
    _require_kb_id(kb_name)
    if not filename:
        raise ValueError("缺少文件名")
    if Path(filename).suffix.lower() not in SUPPORTED_SUFFIXES:
        raise ValueError(f"文件 {filename} 类型不支持，仅支持 {'、'.join(SUPPORTED_SUFFIXES)}")
    pairs = parse_qa_text(decode_text(filename, content), filename)
    if not pairs:
        raise ValueError(f"文件 {filename} 未解析到任何 Q/A 问答对")
    return _replace_document(kb_name, filename, pairs)


def _write_document(kb_name: str, filename: str, pairs: list[tuple[str, str]]) -> dict:
    """仅把文档与问答写入数据库（事务，同名文档先删旧记录）。

    返回新写入的问答记录与需删除的旧问答 id，供迁移导入（纯落库）与上传（落库+向量化）共用。
    """
    kb_id = _require_kb_id(kb_name)
    with get_connection() as con:
        old = con.execute(
            "select id from documents where kb_id = ? and name = ?", (kb_id, filename)
        ).fetchone()
        old_qa_ids = []
        if old:
            old_qa_ids = [
                r["id"]
                for r in con.execute(
                    "select id from qa_items where document_id = ?", (old["id"],)
                ).fetchall()
            ]
            con.execute("delete from documents where id = ?", (old["id"],))  # 级联删除旧问答
        cur = con.execute("insert into documents (kb_id, name) values (?, ?)", (kb_id, filename))
        doc_id = cur.lastrowid
        con.executemany(
            "insert into qa_items (document_id, question, answer, seq) values (?, ?, ?, ?)",
            [(doc_id, q, a, i) for i, (q, a) in enumerate(pairs)],
        )
        rows = con.execute(
            "select id, question, answer from qa_items where document_id = ? order by seq",
            (doc_id,),
        ).fetchall()
    return {
        "doc_id": doc_id,
        "rows": [dict(r) for r in rows],
        "old_qa_ids": old_qa_ids,
        "replaced": old is not None,
    }


def _replace_document(kb_name: str, filename: str, pairs: list[tuple[str, str]]) -> dict:
    """覆盖式写入一个文档：数据库先落库（事务），再增量更新向量集合。"""
    written = _write_document(kb_name, filename, pairs)
    # 向量更新在事务提交后进行；失败只影响索引，重启自检会从数据库补齐
    store = _get_store(kb_name)
    if written["old_qa_ids"]:
        store.delete(ids=[str(i) for i in written["old_qa_ids"]])
    vect_rows = [
        {"id": r["id"], "question": r["question"], "answer": r["answer"], "doc_name": filename}
        for r in written["rows"]
    ]
    store.add_documents(
        [_to_vector_doc(kb_name, r) for r in vect_rows], ids=[str(r["id"]) for r in written["rows"]]
    )
    return {
        "document_id": written["doc_id"],
        "name": filename,
        "qa_count": len(written["rows"]),
        "replaced": written["replaced"],
    }


def list_documents(kb_name: str) -> list[dict]:
    """列出某知识库下的全部文档（含问答总数）。"""
    kb_id = _require_kb_id(kb_name)
    with get_connection() as con:
        rows = con.execute(
            """
            select d.id, d.name,
                   (select count(*) from qa_items where document_id = d.id) as qa_count
            from documents d
            where d.kb_id = ?
            order by d.id
            """,
            (kb_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def _require_document(kb_name: str, document_id: int) -> dict:
    """校验文档存在且属于指定知识库，返回文档行（含所属知识库名）。

    文档属于其他知识库时同样视为不存在（404），不泄露跨库资源归属。
    """
    with get_connection() as con:
        row = con.execute(
            """
            select d.id, d.name, k.name as kb_name
            from documents d
            join knowledge_bases k on k.id = d.kb_id
            where d.id = ?
            """,
            (document_id,),
        ).fetchone()
    if row is None or row["kb_name"] != kb_name:
        raise DocumentNotFoundError(f"知识库 {kb_name!r} 下不存在文档 id={document_id}")
    return dict(row)


def list_qa(kb_name: str, document_id: int) -> list[dict]:
    """列出指定文档下的全部问答对（按录入顺序返回）。"""
    _require_document(kb_name, document_id)
    with get_connection() as con:
        rows = con.execute(
            "select id, question, answer from qa_items where document_id = ? order by seq",
            (document_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_document(kb_name: str, document_id: int) -> None:
    """删除文档：数据库记录（级联删除问答与媒体记录）、对应向量与媒体文件一并删除。"""
    _require_document(kb_name, document_id)
    with get_connection() as con:
        old_qa_ids = [
            r["id"]
            for r in con.execute("select id from qa_items where document_id = ?", (document_id,)).fetchall()
        ]
        con.execute("delete from documents where id = ?", (document_id,))
    store = _get_store(kb_name)
    if old_qa_ids:
        store.delete(ids=[str(i) for i in old_qa_ids])
    _remove_media_files(_media_paths_of_qa_ids(old_qa_ids))


# ---------------------------------------------------------------------------
# 问答修改：改数据库后重写对应向量（向量 id = 问答主键，原地覆盖）
# ---------------------------------------------------------------------------


def _require_qa(kb_name: str, document_id: int, qa_id: int) -> dict:
    """校验问答存在且属于指定知识库的指定文档，返回问答行（含文档名）。

    一次 join 查询同时校验「知识库 -> 文档 -> 问答」整条归属链，任一层不匹配
    均视为不存在（404），不泄露跨库/跨文档资源归属。
    """
    with get_connection() as con:
        row = con.execute(
            """
            select qi.id, qi.document_id, d.name as doc_name, k.name as kb_name
            from qa_items qi
            join documents d on d.id = qi.document_id
            join knowledge_bases k on k.id = d.kb_id
            where qi.id = ?
            """,
            (qa_id,),
        ).fetchone()
    if row is None or row["kb_name"] != kb_name or row["document_id"] != document_id:
        raise QaItemNotFoundError(
            f"知识库 {kb_name!r} 的文档 id={document_id} 下不存在问答 id={qa_id}"
        )
    return dict(row)


def add_qa(kb_name: str, document_id: int, question: str, answer: str) -> dict:
    """在指定文档末尾追加一条问答并写入对应向量。

    seq 取当前文档内最大值 +1（保证顺序），并发冲突时按唯一约束重试取号。
    """
    doc = _require_document(kb_name, document_id)
    for attempt in range(3):
        try:
            with get_connection() as con:
                cur_max = con.execute(
                    "select coalesce(max(seq), -1) from qa_items where document_id = ?",
                    (document_id,),
                ).fetchone()[0]
                cur = con.execute(
                    "insert into qa_items (document_id, question, answer, seq) values (?, ?, ?, ?)",
                    (document_id, question, answer, cur_max + 1),
                )
                qa_id = cur.lastrowid
            break
        except sqlite3.IntegrityError as exc:
            if attempt == 2:
                raise ValueError("问答编号冲突，追加失败，请重试") from exc
    store = _get_store(kb_name)
    store.add_documents(
        [
            _to_vector_doc(
                kb_name, {"id": qa_id, "question": question, "answer": answer, "doc_name": doc["name"]}
            )
        ],
        ids=[str(qa_id)],
    )
    return {"id": qa_id, "question": question, "answer": answer}


def update_qa(kb_name: str, document_id: int, qa_id: int, question: str, answer: str) -> dict:
    """修改一条问答记录并同步更新其向量索引单元。"""
    row = _require_qa(kb_name, document_id, qa_id)
    with get_connection() as con:
        con.execute(
            "update qa_items set question = ?, answer = ? where id = ?",
            (question, answer, qa_id),
        )
    store = _get_store(kb_name)
    store.delete(ids=[str(qa_id)])
    store.add_documents(
        [
            _to_vector_doc(
                kb_name, {"id": qa_id, "question": question, "answer": answer, "doc_name": row["doc_name"]}
            )
        ],
        ids=[str(qa_id)],
    )
    return {"id": qa_id, "question": question, "answer": answer}


def delete_qa(kb_name: str, document_id: int, qa_id: int) -> None:
    """删除一条问答：数据库记录（级联删除媒体记录）、对应向量与媒体文件一并删除。"""
    _require_qa(kb_name, document_id, qa_id)
    media_paths = _media_paths_of_qa_ids([qa_id])
    with get_connection() as con:
        con.execute("delete from qa_items where id = ?", (qa_id,))
    store = _get_store(kb_name)
    store.delete(ids=[str(qa_id)])
    _remove_media_files(media_paths)


# ---------------------------------------------------------------------------
# 媒体附件：文件按「问答 id / uuid.后缀」落盘，数据库存元数据与相对路径。
# 媒体不参与向量化，仅作为佐证材料；文件-记录一致性靠「即时清理 + 启动孤儿兜底」保证。
# ---------------------------------------------------------------------------


def _media_url(kb_name: str, document_id: int, qa_id: int, media_id: int) -> str:
    """媒体内容访问地址（前端带登录令牌请求该地址即可取到文件）。"""
    return (
        f"/document/knowledge-bases/{kb_name}/documents/{document_id}"
        f"/qa/{qa_id}/media/{media_id}/content"
    )


def _require_media(kb_name: str, document_id: int, qa_id: int, media_id: int) -> dict:
    """校验媒体存在且属于指定「知识库 -> 文档 -> 问答」链，返回元数据行（含磁盘绝对路径）。

    任一层归属不匹配均视为不存在（404），不泄露跨库/跨文档资源归属。
    """
    with get_connection() as con:
        row = con.execute(
            """
            select ma.id, ma.qa_id, ma.filename, ma.mime_type, ma.size, ma.stored_path,
                   d.id as document_id, k.name as kb_name
            from media_assets ma
            join qa_items qi on qi.id = ma.qa_id
            join documents d on d.id = qi.document_id
            join knowledge_bases k on k.id = d.kb_id
            where ma.id = ?
            """,
            (media_id,),
        ).fetchone()
    if (
        row is None
        or row["kb_name"] != kb_name
        or row["document_id"] != document_id
        or row["qa_id"] != qa_id
    ):
        raise MediaNotFoundError(
            f"知识库 {kb_name!r} 的文档 id={document_id} 问答 id={qa_id} 下不存在媒体 id={media_id}"
        )
    info = dict(row)
    info["path"] = document_settings.media_root / info.pop("stored_path")
    if not info["path"].is_file():
        raise MediaNotFoundError(f"媒体 id={media_id} 的磁盘文件缺失，可能已被清理")
    return info


def save_media(
    kb_name: str, document_id: int, qa_id: int, filename: str, content: bytes, mime_type: str
) -> dict:
    """保存一条问答的媒体附件：文件落盘 + 数据库记录元数据。"""
    _require_qa(kb_name, document_id, qa_id)
    if not filename:
        raise ValueError("缺少文件名")
    suffix = Path(filename).suffix.lower()
    if suffix not in MEDIA_SUFFIXES:
        raise ValueError(f"文件 {filename} 类型不支持，仅支持 {'、'.join(MEDIA_SUFFIXES)}")
    if not content:
        raise ValueError(f"文件 {filename} 内容为空")
    if len(content) > MAX_MEDIA_SIZE_BYTES:
        limit_mb = MAX_MEDIA_SIZE_BYTES // 1024 // 1024
        raise ValueError(f"文件 {filename} 超过大小上限 {limit_mb}MB")
    if not mime_type:
        mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    # 磁盘文件名用 uuid 重命名，杜绝用户文件名引入路径穿越风险
    stored_name = uuid.uuid4().hex + suffix
    qa_dir = document_settings.media_root / str(qa_id)
    qa_dir.mkdir(parents=True, exist_ok=True)
    (qa_dir / stored_name).write_bytes(content)
    with get_connection() as con:
        cur = con.execute(
            """
            insert into media_assets (qa_id, filename, stored_path, mime_type, size)
            values (?, ?, ?, ?, ?)
            """,
            (qa_id, filename, f"{qa_id}/{stored_name}", mime_type, len(content)),
        )
        media_id = cur.lastrowid
    return {
        "id": media_id,
        "qa_id": qa_id,
        "filename": filename,
        "mime_type": mime_type,
        "size": len(content),
        "url": _media_url(kb_name, document_id, qa_id, media_id),
    }


def list_media(kb_name: str, document_id: int, qa_id: int) -> list[dict]:
    """列出指定问答下的全部媒体附件。"""
    _require_qa(kb_name, document_id, qa_id)
    with get_connection() as con:
        rows = con.execute(
            "select id, qa_id, filename, mime_type, size from media_assets where qa_id = ? order by id",
            (qa_id,),
        ).fetchall()
    return [
        {**dict(r), "url": _media_url(kb_name, document_id, qa_id, r["id"])} for r in rows
    ]


def get_media(kb_name: str, document_id: int, qa_id: int, media_id: int) -> dict:
    """读取一条媒体附件：校验归属链，返回元数据与磁盘绝对路径（供内容接口回传文件）。"""
    return _require_media(kb_name, document_id, qa_id, media_id)


def delete_media(kb_name: str, document_id: int, qa_id: int, media_id: int) -> None:
    """删除一条媒体附件：数据库记录与磁盘文件一并删除。"""
    info = _require_media(kb_name, document_id, qa_id, media_id)
    with get_connection() as con:
        con.execute("delete from media_assets where id = ?", (media_id,))
    _remove_media_files([info["path"]])


def list_media_by_qa_ids(qa_ids: list[int]) -> list[dict]:
    """按问答 id 批量取媒体附件（供 agent 把媒体随 invoke 答案返回）。"""
    if not qa_ids:
        return []
    marks = ",".join("?" * len(qa_ids))
    with get_connection() as con:
        rows = con.execute(
            f"""
            select ma.id, ma.qa_id, ma.filename, ma.mime_type, ma.size,
                   d.id as document_id, k.name as kb_name
            from media_assets ma
            join qa_items qi on qi.id = ma.qa_id
            join documents d on d.id = qi.document_id
            join knowledge_bases k on k.id = d.kb_id
            where ma.qa_id in ({marks})
            order by ma.id
            """,
            tuple(qa_ids),
        ).fetchall()
    return [
        {
            "id": r["id"],
            "qa_id": r["qa_id"],
            "filename": r["filename"],
            "mime_type": r["mime_type"],
            "size": r["size"],
            "url": _media_url(r["kb_name"], r["document_id"], r["qa_id"], r["id"]),
        }
        for r in rows
    ]


def _media_paths_of_qa_ids(qa_ids: list[int]) -> list[Path]:
    """查询问答批量对应的媒体磁盘路径（须在数据库级联删除前调用）。"""
    if not qa_ids:
        return []
    marks = ",".join("?" * len(qa_ids))
    with get_connection() as con:
        rows = con.execute(
            f"select stored_path from media_assets where qa_id in ({marks})", tuple(qa_ids)
        ).fetchall()
    return [document_settings.media_root / r["stored_path"] for r in rows]


def _remove_media_files(paths: list[Path]) -> None:
    """删除媒体文件（失败仅告警，孤儿文件由启动清理兜底）。"""
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            _log(f"媒体文件 {path} 暂被占用未删除（{exc}），下次启动清理")
            continue
        try:
            path.parent.rmdir()  # 目录已空则一并删除
        except OSError:
            continue


def _remove_orphan_media_files() -> None:
    """清理数据库中已无记录的媒体文件与空目录（删除时被占用的文件在此兜底清理）。"""
    root = document_settings.media_root
    if not root.is_dir():
        return
    with get_connection() as con:
        kept = {
            r["stored_path"] for r in con.execute("select stored_path from media_assets").fetchall()
        }
    removed = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel not in kept:
            try:
                path.unlink()
                removed.append(rel)
            except OSError as exc:
                _log(f"孤儿媒体文件 {rel} 暂被占用未清理（{exc}）")
    for dirpath in sorted([p for p in root.rglob("*") if p.is_dir()], key=str, reverse=True):
        try:
            dirpath.rmdir()
        except OSError:
            pass
    if removed:
        _log(f"清理 {len(removed)} 个孤儿媒体文件：{removed}")


# ---------------------------------------------------------------------------
# 内部统计
# ---------------------------------------------------------------------------


def _count_qas(kb_name: str) -> int:
    with get_connection() as con:
        return con.execute(
            """
            select count(*)
            from qa_items qi
            join documents d on d.id = qi.document_id
            join knowledge_bases k on k.id = d.kb_id
            where k.name = ?
            """,
            (kb_name,),
        ).fetchone()[0]