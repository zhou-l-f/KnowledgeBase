"""生成层评测 harness（Phase 3）：跑完整 RAG 问答，再用 LLM-as-judge 判定答案质量。

指标：
- 答案正确性（正样本）：模型答案与参考答案的一致程度，correct=1 / partial=0.5 / incorrect=0
- 答案忠实度（正样本）：答案是否由检索资料支持，faithful=1 / partial=0.5 / unfaithful=0
- 拒答准确率（负样本）：知识库无答案时是否正确回答「根据已有资料无法回答」

降噪：LLM 判定存在单次波动（实测约 1/样本数），故支持 --repeat 多次运行取均值并给出标准差；
**小于标准差的指标差不可信**，不要当成优化收益。

调用生产链路 src.agent.service.answer_with_context，故评测即线上行为。

用法（在 backend/ 目录下，需可用的 DEEPSEEK_API_KEY）：
    python -m eval.run_answer_eval --tag answer_v1 --repeat 3
    python -m eval.run_answer_eval --tag answer_v1 --limit 10 --concurrency 6   # 小样本试跑
    python -m eval.run_answer_eval --tag answer_v2 --repeat 3 --compare-with answer_v1
"""

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import argparse  # noqa: E402
import asyncio  # noqa: E402
import json  # noqa: E402
import statistics  # noqa: E402
import time  # noqa: E402
from datetime import datetime  # noqa: E402

from eval.judge import is_refusal, judge_correctness, judge_faithfulness  # noqa: E402
from eval.run_retrieval_eval import DATASET_PATH, REPORTS_DIR, load_dataset  # noqa: E402
from src.agent import service as agent_service  # noqa: E402
from src.agent.config import agent_settings  # noqa: E402
from src.database import get_connection  # noqa: E402

# 参与均值/标准差的指标
METRIC_KEYS = ("correctness", "faithfulness", "refusal_accuracy")
METRIC_LABELS = {"correctness": "答案正确性", "faithfulness": "答案忠实度", "refusal_accuracy": "拒答准确率"}


def build_reference_index() -> dict[tuple[str, str], str]:
    """构建 (知识库名, 问题文本) -> 参考答案 的索引。"""
    with get_connection() as con:
        rows = con.execute(
            """
            select qi.question, qi.answer, k.name as kb_name
            from qa_items qi
            join documents d on d.id = qi.document_id
            join knowledge_bases k on k.id = d.kb_id
            """
        ).fetchall()
    return {(r["kb_name"], r["question"].strip()): r["answer"] for r in rows}


async def evaluate_sample(sample: dict, index: dict[tuple[str, str], str], sem: asyncio.Semaphore) -> dict:
    """对单条样本跑完整 RAG 并判定，返回逐样本结果。"""
    async with sem:
        row = {
            "id": sample["id"],
            "kb_name": sample["kb_name"],
            "type": sample.get("type", ""),
            "question": sample["question"],
        }
        try:
            answer, hits = await agent_service.answer_with_context(sample["question"], sample["kb_name"])
        except Exception as exc:  # 单条失败不影响整体
            return {**row, "error": str(exc)}
        row["answer"] = answer

        if not sample.get("expect_question"):
            # 负样本：期望拒答
            row["refusal_correct"] = is_refusal(answer, agent_service.REFUSAL_ANSWER)
            return row

        reference = index.get((sample["kb_name"], sample["expect_question"].strip()))
        if reference is None:
            row["error"] = "参考答案无法解析（测试集与库不一致）"
            return row
        context = "\n\n".join(hit.page_content for hit in hits)
        row["reference"] = reference
        row["correctness"] = await judge_correctness(sample["question"], reference, answer)
        row["faithfulness"] = await judge_faithfulness(context, answer)
        return row


def summarize(rows: list[dict]) -> dict:
    """聚合单次运行的逐样本结果。"""
    positives = [r for r in rows if not r.get("error") and r.get("correctness")]
    negatives = [r for r in rows if not r.get("error") and "refusal_correct" in r]
    errors = [r for r in rows if r.get("error")]

    def dist(source: list[dict], key: str) -> dict:
        counts: dict[str, int] = {}
        for r in source:
            verdict = r.get(key, {}).get("verdict", "?")
            counts[verdict] = counts.get(verdict, 0) + 1
        return counts

    positive_count = len(positives)
    return {
        "positive_count": positive_count,
        "negative_count": len(negatives),
        "error_count": len(errors),
        "correctness": round(sum(r["correctness"]["score"] for r in positives) / positive_count, 4)
        if positive_count
        else 0.0,
        "faithfulness": round(sum(r["faithfulness"]["score"] for r in positives) / positive_count, 4)
        if positive_count
        else 0.0,
        "refusal_accuracy": round(sum(1 for r in negatives if r["refusal_correct"]) / len(negatives), 4)
        if negatives
        else 0.0,
        "correctness_dist": dist(positives, "correctness"),
        "faithfulness_dist": dist(positives, "faithfulness"),
    }


def aggregate_runs(summaries: list[dict]) -> tuple[dict, dict]:
    """多次运行的汇总：返回 (均值, 标准差)。标准差即 LLM 判定的波动幅度。"""
    mean = {}
    std = {}
    for key in METRIC_KEYS:
        values = [s[key] for s in summaries]
        mean[key] = round(statistics.fmean(values), 4)
        std[key] = round(statistics.pstdev(values), 4) if len(values) > 1 else 0.0
    return mean, std


async def one_pass(samples: list[dict], index: dict, sem: asyncio.Semaphore) -> dict:
    started = time.perf_counter()
    rows = await asyncio.gather(*[evaluate_sample(s, index, sem) for s in samples])
    return {"elapsed_sec": round(time.perf_counter() - started, 2), "summary": summarize(list(rows)), "samples": list(rows)}


async def run(tag: str, note: str, samples: list[dict], concurrency: int, repeat: int) -> dict:
    index = build_reference_index()
    sem = asyncio.Semaphore(concurrency)
    started = time.perf_counter()
    passes = []
    for i in range(repeat):
        if repeat > 1:
            print(f"[第 {i + 1}/{repeat} 轮] 评测中…", flush=True)
        passes.append(await one_pass(samples, index, sem))
    summaries = [p["summary"] for p in passes]
    mean, std = aggregate_runs(summaries)
    return {
        "tag": tag,
        "note": note,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "elapsed_sec": round(time.perf_counter() - started, 2),
        "config": {
            "deepseek_model": agent_settings.deepseek_model,
            "retrieval_k": agent_settings.retrieval_k,
            "rerank_enabled": agent_settings.rerank_enabled,
            "concurrency": concurrency,
            "repeat": repeat,
        },
        "summary": {**mean, "positive_count": summaries[-1]["positive_count"], "negative_count": summaries[-1]["negative_count"], "error_count": summaries[-1]["error_count"], "correctness_dist": summaries[-1]["correctness_dist"], "faithfulness_dist": summaries[-1]["faithfulness_dist"]},
        "summary_std": std,
        "runs": [{"elapsed_sec": p["elapsed_sec"], "summary": p["summary"]} for p in passes],
        "samples": passes[-1]["samples"],  # 仅保留最后一轮的逐样本明细，供排查
    }


def print_report(report: dict) -> None:
    s = report["summary"]
    std = report["summary_std"]
    cfg = report["config"]
    print(f"\n===== 生成层评测 [{report['tag']}] =====", flush=True)
    print(f"时间：{report['generated_at']}    耗时：{report['elapsed_sec']}s", flush=True)
    print(
        f"配置：模型={cfg['deepseek_model']}  k={cfg['retrieval_k']}  重排={cfg['rerank_enabled']}  "
        f"并发={cfg['concurrency']}  重复={cfg['repeat']}",
        flush=True,
    )
    if report["note"]:
        print(f"说明：{report['note']}", flush=True)
    print(
        f"样本：正样本 {s['positive_count']} / 负样本 {s['negative_count']} / 失败 {s['error_count']}",
        flush=True,
    )
    print("\n-- 总体指标（均值 ± 判定波动） --", flush=True)
    for key in METRIC_KEYS:
        print(f"  {METRIC_LABELS[key]:<12} {s[key]:.3f} ± {std[key]:.3f}", flush=True)
    if cfg["repeat"] > 1:
        worst = max(std.values())
        print(f"  [提示] 判定波动最大 ±{worst:.3f}，小于该幅度的指标差不可信", flush=True)
    print(f"  正确性分布 {s['correctness_dist']}    忠实度分布 {s['faithfulness_dist']}", flush=True)

    bad = [
        r
        for r in report["samples"]
        if r.get("error")
        or (r.get("correctness") and r["correctness"]["verdict"] != "correct")
        or r.get("refusal_correct") is False
    ]
    if bad:
        print(f"\n-- 问题样本（{len(bad)}，末轮）--", flush=True)
        for r in bad:
            if r.get("error"):
                print(f"  [{r['id']}] 失败：{r['error']}", flush=True)
            elif r.get("refusal_correct") is False:
                print(f"  [{r['id']}] 负样本未拒答：{r['answer'][:50]}", flush=True)
            else:
                print(
                    f"  [{r['id']}] {r['correctness']['verdict']} | {r['question']} | 答：{r['answer'][:40]}",
                    flush=True,
                )


def compare(tag: str, base_tag: str) -> None:
    base = json.loads((REPORTS_DIR / f"{base_tag}.json").read_text(encoding="utf-8"))
    cur = json.loads((REPORTS_DIR / f"{tag}.json").read_text(encoding="utf-8"))
    print(f"\n===== 对比 [{base_tag}] -> [{tag}] =====", flush=True)
    print(f"{'指标':<12}{base_tag:>16}{tag:>16}{'变化':>12}{'波动':>10}", flush=True)
    for key in METRIC_KEYS:
        b, c = base["summary"][key], cur["summary"][key]
        delta = c - b
        arrow = "↑" if delta > 0 else ("↓" if delta < 0 else "=")
        noise = max(base.get("summary_std", {}).get(key, 0.0), cur.get("summary_std", {}).get(key, 0.0))
        mark = "" if abs(delta) > noise else "(噪声内)"
        print(f"{METRIC_LABELS[key]:<12}{b:>16.3f}{c:>16.3f}{arrow + format(abs(delta), '.3f'):>12}{noise:>10.3f} {mark}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="生成层评测 harness")
    parser.add_argument("--tag", required=True, help="本次运行的标签，报告存为 reports/<tag>.json")
    parser.add_argument("--note", default="", help="配置变更说明")
    parser.add_argument("--limit", type=int, default=None, help="只跑前 N 条（小样本试跑）")
    parser.add_argument("--concurrency", type=int, default=4, help="并发请求数")
    parser.add_argument("--repeat", type=int, default=1, help="重复运行次数，>1 时取均值以降低判定噪声")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH, help="测试集路径")
    parser.add_argument("--compare-with", default=None, help="与已有报告标签对比")
    args = parser.parse_args()

    samples = load_dataset(args.dataset)
    if args.limit:
        samples = samples[: args.limit]
    report = asyncio.run(run(args.tag, args.note, samples, args.concurrency, args.repeat))

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / f"{args.tag}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print_report(report)
    print(f"\n报告已写入：{out_path}", flush=True)

    if args.compare_with:
        compare(args.tag, args.compare_with)


if __name__ == "__main__":
    main()
