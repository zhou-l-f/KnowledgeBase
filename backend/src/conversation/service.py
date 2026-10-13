"""会话模块服务层：历史对话记录（会话 + 消息）的持久化真源。

职责边界：
- 本模块是对话记忆的唯一真源：会话按登录用户归属，消息随会话落库；
- 会话与消息 id 使用 UUID 字符串、时间使用毫秒时间戳，与前端会话数据结构对齐；
- 消息中的引用来源（sources）与媒体附件（media）以 JSON 文本原样存储，
  媒体文件本体仍由 document 模块管理，本模块只保存其元数据快照；
- 面向 agent 模块提供多轮记忆的历史加载（load_history）与问答落库
  （start_conversation / append_exchange），agent 不直接读写会话表。
"""

import json
import time
import uuid

from src.conversation.exceptions import ConversationNotFoundError
from src.database import get_connection

# 多轮记忆窗口：喂给 LLM 的历史消息条数上限
HISTORY_LIMIT = 10

# 会话标题规则（与前端首问生成标题一致）：压缩空白、超长截断
_TITLE_MAX_LEN = 18
_DEFAULT_TITLE = "新对话"


def init() -> None:
    """启动初始化：建表（幂等）。"""
    _init_db()
    print("[conversation] 会话模块初始化完成（会话/消息表就绪）", flush=True)


def _init_db() -> None:
    """创建会话与消息两张表（幂等）。

    外键开启级联删除，删除会话即删其全部消息；用户归属校验靠查询时比对 user_id。
    """
    with get_connection() as con:
        con.executescript(
            """
            create table if not exists conversations (
                id text primary key,
                user_id text not null,
                kb_name text not null,
                title text not null,
                created_at integer not null,
                updated_at integer not null
            );
            create table if not exists messages (
                id text primary key,
                conversation_id text not null references conversations(id) on delete cascade,
                role text not null,
                content text not null,
                sources text not null default '[]',
                media text not null default '[]',
                status text not null default 'done',
                created_at integer not null
            );
            create index if not exists idx_conversations_user
                on conversations(user_id, updated_at desc);
            create index if not exists idx_messages_conversation
                on messages(conversation_id, created_at);
            """
        )


def _now_ms() -> int:
    return int(time.time() * 1000)


def derive_title(question: str) -> str:
    """用首个问题生成会话标题：压缩连续空白，超长截断加省略号。"""
    clean = " ".join(question.split())
    if not clean:
        return _DEFAULT_TITLE
    return clean[:_TITLE_MAX_LEN] + "…" if len(clean) > _TITLE_MAX_LEN else clean


def _conversation_out(row: dict) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "kb_name": row["kb_name"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _message_out(row: dict) -> dict:
    return {
        "id": row["id"],
        "role": row["role"],
        "content": row["content"],
        "sources": json.loads(row["sources"]),
        "media": json.loads(row["media"]),
        "status": row["status"],
        "created_at": row["created_at"],
    }


def _require_conversation(user_id: str, conversation_id: str) -> dict:
    """校验会话存在且属于当前用户，返回会话行；其余情况一律抛 404。

    非本人会话视为不存在，不泄露他人会话的存在性。
    """
    with get_connection() as con:
        row = con.execute(
            "select id, user_id, kb_name, title, created_at, updated_at "
            "from conversations where id = ?",
            (conversation_id,),
        ).fetchone()
    if row is None or row["user_id"] != user_id:
        raise ConversationNotFoundError(f"会话 {conversation_id!r} 不存在")
    return dict(row)


# ---------------------------------------------------------------------------
# 会话 CRUD
# ---------------------------------------------------------------------------


def list_conversations(user_id: str) -> list[dict]:
    """列出当前用户的全部会话（按最近更新倒序）。"""
    with get_connection() as con:
        rows = con.execute(
            "select id, title, kb_name, created_at, updated_at "
            "from conversations where user_id = ? order by updated_at desc",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_conversation(user_id: str, conversation_id: str) -> dict:
    """获取会话详情（含全部消息，按插入顺序）。"""
    row = _require_conversation(user_id, conversation_id)
    with get_connection() as con:
        rows = con.execute(
            "select id, role, content, sources, media, status, created_at "
            "from messages where conversation_id = ? order by created_at, rowid",
            (conversation_id,),
        ).fetchall()
    detail = _conversation_out(row)
    detail["messages"] = [_message_out(dict(r)) for r in rows]
    return detail


def delete_conversation(user_id: str, conversation_id: str) -> None:
    """删除会话及其全部消息（消息按外键级联删除）。"""
    _require_conversation(user_id, conversation_id)
    with get_connection() as con:
        con.execute("delete from conversations where id = ?", (conversation_id,))


# ---------------------------------------------------------------------------
# 多轮记忆：历史加载与问答落库（供 agent 模块调用）
# ---------------------------------------------------------------------------


def load_history(user_id: str, conversation_id: str, limit: int = HISTORY_LIMIT) -> list[dict]:
    """加载会话最近 limit 条消息（按时间正序返回），供多轮记忆拼入 prompt。"""
    _require_conversation(user_id, conversation_id)
    with get_connection() as con:
        rows = con.execute(
            "select role, content from messages where conversation_id = ? "
            "order by created_at desc, rowid desc limit ?",
            (conversation_id, limit),
        ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def _exchange_rows(
    conversation_id: str, question: str, answer: str, sources: list[str], media: list[dict], ts: int
) -> list[tuple]:
    """构造一轮问答的两条消息记录（用户问题 + 助手回答），引用与媒体存 JSON。"""
    return [
        (str(uuid.uuid4()), conversation_id, "user", question, "[]", "[]", "done", ts),
        (
            str(uuid.uuid4()),
            conversation_id,
            "assistant",
            answer,
            json.dumps(sources, ensure_ascii=False),
            json.dumps(media, ensure_ascii=False),
            "done",
            ts,
        ),
    ]


def start_conversation(
    user_id: str,
    kb_name: str,
    question: str,
    answer: str,
    sources: list[str],
    media: list[dict],
) -> str:
    """新建会话并写入首轮问答，返回新会话 id（标题由首个问题生成）。"""
    conversation_id = str(uuid.uuid4())
    now = _now_ms()
    with get_connection() as con:
        con.execute(
            "insert into conversations (id, user_id, kb_name, title, created_at, updated_at) "
            "values (?, ?, ?, ?, ?, ?)",
            (conversation_id, user_id, kb_name, derive_title(question), now, now),
        )
        con.executemany(
            "insert into messages "
            "(id, conversation_id, role, content, sources, media, status, created_at) "
            "values (?, ?, ?, ?, ?, ?, ?, ?)",
            _exchange_rows(conversation_id, question, answer, sources, media, now),
        )
    return conversation_id


def append_exchange(
    user_id: str,
    conversation_id: str,
    question: str,
    answer: str,
    sources: list[str],
    media: list[dict],
) -> None:
    """向已有会话追加一轮问答，并刷新会话更新时间。"""
    _require_conversation(user_id, conversation_id)
    now = _now_ms()
    with get_connection() as con:
        con.executemany(
            "insert into messages "
            "(id, conversation_id, role, content, sources, media, status, created_at) "
            "values (?, ?, ?, ?, ?, ?, ?, ?)",
            _exchange_rows(conversation_id, question, answer, sources, media, now),
        )
        con.execute(
            "update conversations set updated_at = ? where id = ?", (now, conversation_id)
        )