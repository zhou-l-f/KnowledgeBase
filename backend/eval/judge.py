"""生成层评测的 LLM-as-judge：判定答案正确性与忠实度。

判定统一由 DeepSeek（复用 agent 的模型配置）执行，返回结构化结果：
- 正确性：模型答案与参考答案是否实质一致（correct / partial / incorrect）
- 忠实度：模型答案的每个事实是否都能由检索到的资料支持（faithful / partial / unfaithful）

判定模型与生成模型同源，存在"自评偏差"的可能，结论宜作为趋势参考而非绝对结论。
"""

import json
import re

from langchain_openai import ChatOpenAI

from src.agent.config import agent_settings

# 各类判定的分档与得分映射
CORRECTNESS_SCORES = {"correct": 1.0, "partial": 0.5, "incorrect": 0.0}
FAITHFULNESS_SCORES = {"faithful": 1.0, "partial": 0.5, "unfaithful": 0.0}

CORRECTNESS_PROMPT = """你是严格的答案评审员。根据【问题】【参考答案】【模型回答】判断模型回答是否与参考答案实质一致。
判定标准：
- correct：涵盖参考答案的关键信息且无冲突；
- partial：部分涵盖，信息不完整但无明显冲突；
- incorrect：与参考答案冲突、答非所问，或声称无法回答。
注意：只就【问题】所问的内容比较；参考答案中与问题无关的额外信息不作为扣分依据。
只输出 JSON，不要多余文字：{{"verdict": "correct|partial|incorrect", "reason": "一句话理由"}}

【问题】{question}
【参考答案】{reference}
【模型回答】{answer}"""

FAITHFULNESS_PROMPT = """你是严格的忠实度评审员。判断【模型回答】中的每个事实是否都能由【资料】支持。
判定标准：
- faithful：所有事实均能在资料中找到依据；
- partial：部分事实缺乏资料依据；
- unfaithful：大量内容无资料依据或属于编造。
只输出 JSON，不要多余文字：{{"verdict": "faithful|partial|unfaithful", "reason": "一句话理由"}}

【资料】{context}
【模型回答】{answer}"""

_judge_llm: ChatOpenAI | None = None


def _get_llm() -> ChatOpenAI:
    """判定用 LLM（进程内单例，复用 agent 的 DeepSeek 配置）。"""
    global _judge_llm
    if _judge_llm is None:
        if not agent_settings.deepseek_api_key:
            raise ValueError("未配置 DEEPSEEK_API_KEY，无法进行 LLM 判定")
        _judge_llm = ChatOpenAI(
            model=agent_settings.deepseek_model,
            api_key=agent_settings.deepseek_api_key,
            base_url=agent_settings.deepseek_base_url,
            temperature=0,
        )
    return _judge_llm


def _parse_verdict(text: str) -> str:
    """从模型输出中提取 verdict 字段，容忍 ``` 包裹等噪声。"""
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        return str(json.loads(cleaned).get("verdict", "")).strip().lower()
    except json.JSONDecodeError:
        match = re.search(r'"verdict"\s*:\s*"([^"]+)"', text)
        return match.group(1).strip().lower() if match else ""


async def judge_correctness(question: str, reference: str, answer: str) -> dict:
    """判定答案正确性，返回 {"verdict", "score"}。"""
    prompt = CORRECTNESS_PROMPT.format(question=question, reference=reference, answer=answer)
    raw = await _get_llm().ainvoke(prompt)
    verdict = _parse_verdict(raw.content if hasattr(raw, "content") else str(raw))
    return {"verdict": verdict or "incorrect", "score": CORRECTNESS_SCORES.get(verdict, 0.0)}


async def judge_faithfulness(context: str, answer: str) -> dict:
    """判定答案忠实度，返回 {"verdict", "score"}。"""
    prompt = FAITHFULNESS_PROMPT.format(context=context, answer=answer)
    raw = await _get_llm().ainvoke(prompt)
    verdict = _parse_verdict(raw.content if hasattr(raw, "content") else str(raw))
    return {"verdict": verdict or "unfaithful", "score": FAITHFULNESS_SCORES.get(verdict, 0.0)}


def is_refusal(answer: str, refusal_text: str) -> bool:
    """答案是否为拒答（生成层负样本的期望行为）。"""
    return refusal_text in answer
