"""导出数据库中全部问答，辅助半自动构造/维护评测集。

用法（在 backend/ 目录下）：
    python -m eval.dump_qa            # 打印全部问答
    python -m eval.dump_qa 公司规章    # 只看某个知识库

输出为 JSONL（kb_name / source / question），可据此改写问题、补充近义问法与负样本，
再人工筛选后并入 eval/dataset/qa_eval.jsonl。
"""

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import json  # noqa: E402

from src.database import get_connection  # noqa: E402


def main() -> None:
    kb_filter = sys.argv[1] if len(sys.argv) > 1 else None
    sql = """
        select qi.question, d.name as source, k.name as kb_name
        from qa_items qi
        join documents d on d.id = qi.document_id
        join knowledge_bases k on k.id = d.kb_id
    """
    params: tuple = ()
    if kb_filter:
        sql += " where k.name = ?"
        params = (kb_filter,)
    sql += " order by k.id, d.id, qi.seq"
    with get_connection() as con:
        rows = con.execute(sql, params).fetchall()
    for r in rows:
        print(json.dumps(
            {"kb_name": r["kb_name"], "source": r["source"], "question": r["question"]},
            ensure_ascii=False,
        ), flush=True)
    print(f"\n共 {len(rows)} 条问答", flush=True)


if __name__ == "__main__":
    main()
