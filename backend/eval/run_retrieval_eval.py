"""检索层评测 harness：固化基线、度量每一次检索优化的效果。

设计要点：跑分脚本调用生产检索唯一入口 src.agent.service.retrieve，
因此它测的就是线上真实检索；检索侧优化在 retrieve 内实现后，本脚本自动度量其影响。

用法（在 backend/ 目录下执行）：
    python -m eval.run_retrieval_eval --tag baseline            # 固化基线
    python -m eval.run_retrieval_eval --tag v2 --k 6 --note "加入 query 前缀"  # 跑新配置
    python -m eval.run_retrieval_eval --tag v2 --compare-with baseline        # 前后对比
"""

import sys
from pathlib import Path

# 允许以脚本或模块两种方式运行：把 backend 根目录加入 sys.path
_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import argparse  # noqa: E402
import json  # noqa: E402
import time  # noqa: E402
from datetime import datetime  # noqa: E402

from eval.metrics import METRIC_LABELS, aggregate, hit_at, recall_at, reciprocal_rank  # noqa: E402
from src.agent import service as agent_service  # noqa: E402
from src.agent.config import agent_settings  # noqa: E402
from src.database import get_connection  # noqa: E402
from src.document.config import document_settings  # noqa: E402

DATASET_PATH = Path(__file__).resolve().parent / "dataset" / "qa_eval.jsonl"
REPORTS_DIR = Path(__file__).resolve().parent / "reports"


def load_dataset(path: Path) -> list[dict]:
    """读取 JSONL 测试集，跳过空行。"""
    samples = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            samples.append(json.loads(line))
    return samples


def build_expected_index() -> dict[tuple[str, str], int]:
    """从数据库构建 (知识库名, 问题文本) -> 问答 id 的索引，用于把测试集期望解析为 id。

    用问题文本而非问答 id 作为期望，是为了让测试集在文档重新上传（id 变化）后依然有效。
    """
    with get_connection() as con:
        rows = con.execute(
            """
            select qi.id, qi.question, k.name as kb_name
            from qa_items qi
            join documents d on d.id = qi.document_id
            join knowledge_bases k on k.id = d.kb_id
            """
        ).fetchall()
    return {(r["kb_name"], r["question"].strip()): r["id"] for r in rows}


def evaluate(tag: str, k: int | None, note: str, samples: list[dict]) -> dict:
    """对测试集逐条检索并评分，返回报告字典。"""
    index = build_expected_index()
    started = time.perf_counter()
    rows: list[dict] = []
    unresolved: list[str] = []
    negatives: list[dict] = []

    for sample in samples:
        expected_question = sample.get("expect_question")
        if not expected_question:
            # 负样本：检索层不做判定（Chroma 恒返回 top-k），留给生成层评测阶段
            negatives.append({"id": sample["id"], "question": sample["question"], "note": sample.get("note", "")})
            continue

        expected_id = index.get((sample["kb_name"], expected_question.strip()))
        if expected_id is None:
            unresolved.append(sample["id"])
            continue

        hits = agent_service.retrieve(sample["kb_name"], sample["question"], k)
        retrieved_ids = [int(h.metadata["qa_id"]) for h in hits]
        expected = {expected_id}
        effective_k = k or agent_settings.retrieval_k
        row = {
            "id": sample["id"],
            "kb_name": sample["kb_name"],
            "type": sample.get("type", ""),
            "question": sample["question"],
            "expected_qa_id": expected_id,
            "retrieved_qa_ids": retrieved_ids,
            "retrieved_sources": [h.metadata.get("source", "") for h in hits],
            "hit1": hit_at(retrieved_ids, expected, 1),
            "hitk": hit_at(retrieved_ids, expected, effective_k),
            "recall": recall_at(retrieved_ids, expected, effective_k),
            "rr": reciprocal_rank(retrieved_ids, expected),
        }
        rows.append(row)

    report = {
        "tag": tag,
        "note": note,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "elapsed_sec": round(time.perf_counter() - started, 2),
        "config": {
            "embedding_model": document_settings.embedding_model,
            "retrieval_k_default": agent_settings.retrieval_k,
            "effective_k": k or agent_settings.retrieval_k,
            "query_use_instruction": agent_settings.query_use_instruction,
            "rerank_enabled": agent_settings.rerank_enabled,
            "rerank_model": agent_settings.rerank_model if agent_settings.rerank_enabled else None,
            "rerank_recall_k": agent_settings.rerank_recall_k if agent_settings.rerank_enabled else None,
        },
        "dataset": {
            "total": len(samples),
            "positive": len(rows),
            "negative": len(negatives),
        },
        "summary": aggregate(rows),
        "unresolved": unresolved,
        "negatives": negatives,
        "samples": rows,
    }
    return report


def print_report(report: dict) -> None:
    """在终端打印人可读的汇总。"""
    cfg = report["config"]
    ds = report["dataset"]
    print(f"\n===== 检索评测 [{report['tag']}] =====", flush=True)
    print(f"时间：{report['generated_at']}    耗时：{report['elapsed_sec']}s", flush=True)
    print(f"配置：模型={cfg['embedding_model']}  k={cfg['effective_k']}  query前缀={cfg['query_use_instruction']}", flush=True)
    if cfg["rerank_enabled"]:
        print(f"      重排=开（{cfg['rerank_model']}，召回 {cfg['rerank_recall_k']} 条后精排）", flush=True)
    if report["note"]:
        print(f"说明：{report['note']}", flush=True)
    print(f"样本：正样本 {ds['positive']} / 负样本 {ds['negative']}（负样本本版不计分）", flush=True)

    print("\n-- 总体指标 --", flush=True)
    for key, label in METRIC_LABELS.items():
        print(f"  {label:<10} {report['summary'][key]:.3f}", flush=True)

    misses = [s for s in report["samples"] if not s["hitk"]]
    if misses:
        print(f"\n-- 未命中样本（{len(misses)}）--", flush=True)
        for s in misses:
            print(f"  [{s['id']}] {s['question']}  期望 id={s['expected_qa_id']} 实际={s['retrieved_qa_ids']}", flush=True)
    if report["unresolved"]:
        print(f"\n[警告] 期望无法解析（问题不在库中，需修正测试集）：{report['unresolved']}", flush=True)


def compare(tag: str, base_tag: str) -> None:
    """打印两个报告的指标对比表，用于衡量一次优化的收益。"""
    base = json.loads((REPORTS_DIR / f"{base_tag}.json").read_text(encoding="utf-8"))
    cur = json.loads((REPORTS_DIR / f"{tag}.json").read_text(encoding="utf-8"))
    print(f"\n===== 对比 [{base_tag}] -> [{tag}] =====", flush=True)
    print(f"{'指标':<12}{base_tag:>12}{tag:>12}{'变化':>12}", flush=True)
    for key, label in METRIC_LABELS.items():
        b, c = base["summary"][key], cur["summary"][key]
        delta = c - b
        arrow = "↑" if delta > 0 else ("↓" if delta < 0 else "=")
        print(f"{label:<12}{b:>12.3f}{c:>12.3f}{arrow + format(abs(delta), '.3f'):>12}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="检索层评测 harness")
    parser.add_argument("--tag", required=True, help="本次运行的标签，报告存为 reports/<tag>.json")
    parser.add_argument("--k", type=int, default=None, help="检索 top-k，缺省用配置中的 retrieval_k")
    parser.add_argument("--note", default="", help="本次配置变更说明，写入报告便于回溯")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH, help="测试集路径")
    parser.add_argument("--compare-with", default=None, help="与已有报告标签对比指标")
    args = parser.parse_args()

    samples = load_dataset(args.dataset)
    report = evaluate(args.tag, args.k, args.note, samples)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / f"{args.tag}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print_report(report)
    print(f"\n报告已写入：{out_path}", flush=True)

    if args.compare_with:
        compare(args.tag, args.compare_with)


if __name__ == "__main__":
    main()
