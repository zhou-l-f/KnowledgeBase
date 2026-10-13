"""检索层评测指标：纯函数实现，不依赖具体检索实现，便于复用与单测。

约定：retrieved 为按相关性降序排列的问答 id 列表（第 1 项为 top-1）；
expected 为该问题的应命中文档 id 集合（可为空，表示负样本）。
"""


def hit_at(retrieved: list[int], expected: set[int], k: int) -> bool:
    """top-k 内是否命中任一应命中文档。"""
    return bool(expected & set(retrieved[:k]))


def recall_at(retrieved: list[int], expected: set[int], k: int) -> float:
    """top-k 覆盖了多少比例的应命中文档（单答案样本下等价于 hit）。"""
    if not expected:
        return 0.0
    return len(expected & set(retrieved[:k])) / len(expected)


def reciprocal_rank(retrieved: list[int], expected: set[int]) -> float:
    """第一个命中项的倒数排名（top-1 命中=1.0，第 2 命中=0.5…），未命中为 0。"""
    for rank, qa_id in enumerate(retrieved, start=1):
        if qa_id in expected:
            return 1.0 / rank
    return 0.0


def aggregate(rows: list[dict]) -> dict:
    """把逐样本评分聚合为总体指标。rows 每项须含 hit1/hitk/recall/rr 字段。"""
    count = len(rows)
    if count == 0:
        return {"count": 0, "hit_rate@1": 0.0, "hit_rate@k": 0.0, "recall@k": 0.0, "mrr": 0.0}
    return {
        "count": count,
        "hit_rate@1": sum(r["hit1"] for r in rows) / count,
        "hit_rate@k": sum(r["hitk"] for r in rows) / count,
        "recall@k": sum(r["recall"] for r in rows) / count,
        "mrr": sum(r["rr"] for r in rows) / count,
    }


# 指标展示顺序与中文名，供报告输出复用
METRIC_LABELS = {
    "hit_rate@1": "命中率@1",
    "hit_rate@k": "命中率@k",
    "recall@k": "召回率@k",
    "mrr": "MRR",
}
