"""RAG 服务层：知识库检索 + DeepSeek 生成（agent 只负责问答链路）。

知识库与向量库的构建、维护已移交 document 模块（src/document），本模块：
- 不再直接操作 Chroma / embedding / 文档解析；
- 仅维护 LLM、LCEL 生成链与 LangGraph 问答图的进程级单例（由 warmup 预热）；
- 检索实例通过 document 模块按知识库名获取。

问答链路以 LangGraph 状态图表达，检索与重排均为图节点：

    START → resolve_kb → retrieve ─┬─(候选多于 top_k 且开启重排)→ rerank ─┐
                                   └─(其余情况)──────────────────────────→ generate → finalize → END

向量召回与重排被抽成复用函数，图节点与检索评测入口 retrieve() 共用同一实现，
以保证评测分数与线上行为一致。

多轮记忆与落库（answer_in_conversation）：
- 会话与消息的持久化由 conversation 模块负责，本模块只做编排——加载历史、
  生成、落库；评测入口（answer / answer_with_context）不落库，保持无状态。
"""

import asyncio
import threading
import time
from typing import TypedDict

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from sentence_transformers import CrossEncoder

from src.agent.config import agent_settings
from src.conversation import service as conversation_service
from src.document import service as document_service

# 可重入锁：仅保护单例（LLM / 生成链 / 重排模型 / 问答图）初始化
_lock = threading.RLock()
_llm: ChatOpenAI | None = None
_chain = None
_reranker: CrossEncoder | None = None
_graph = None

# 资料缺失时的兜底回答文案（生成层评测据此判定"拒答"）
REFUSAL_ANSWER = "根据已有资料无法回答"

# 约束 LLM 仅依据检索到的资料回答，资料缺失时明确说明，不编造
PROMPT_TEMPLATE = (
    "你是一个知识库助手，请严格依据以下资料回答用户问题。\n"
    f"如果资料中没有相关内容，直接回答「{REFUSAL_ANSWER}」，不要编造。\n"
    "只陈述资料中明确写出的内容，不要添加资料未明确陈述的推断或结论。\n\n"
    "资料：\n{context}"
)

# bge 系列模型官方推荐的检索查询指令前缀：只加在「查询」上，文档侧不加
BGE_QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："


class RAGState(TypedDict, total=False):
    """问答图的共享状态：各节点只写入自己负责的键，未写入的键视为缺省。"""

    question: str  # 用户问题原文
    kb_name: str | None  # 目标知识库名，resolve_kb 节点后必为有效名
    history: list[BaseMessage]  # 多轮对话历史（按时间正序），无历史时为空
    top_k: int  # 最终喂给 LLM 的文档条数
    candidates: list[Document]  # 向量召回候选（可能多于 top_k）
    hits: list[Document]  # 最终命中（重排结果或直接取候选）
    answer: str  # 模型回答
    sources: list[str]  # 命中文档来源（去重）
    media: list[dict]  # 命中问答的媒体附件


def _log(message: str) -> None:
    """启动进度日志：必须 flush，否则 stdout 被重定向时会全缓冲，导致进度长时间不可见。"""
    print(f"[agent] {message}", flush=True)


def warmup() -> None:
    """启动预热：初始化 LLM 链、重排模型与问答图。

    向量库的构建与自检由 document 模块完成，启动顺序上先于本函数；
    此后知识库增删改由 document 模块维护，agent 不再持有向量库状态。
    """
    started = time.perf_counter()
    _log("启动预热开始（初始化 LLM 链与问答图）")
    _get_chain()
    if agent_settings.rerank_enabled:
        _get_reranker()
    _get_graph()
    _log(f"启动预热完成，LLM 链与问答图就绪，耗时 {time.perf_counter() - started:.1f}s")


# ---------------------------------------------------------------------------
# LLM、生成链与重排模型的懒加载单例
# ---------------------------------------------------------------------------


def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        if not agent_settings.deepseek_api_key:
            raise ValueError("未配置 DEEPSEEK_API_KEY，请在 backend/.env 中填写后重启服务")
        with _lock:
            if _llm is None:
                _llm = ChatOpenAI(
                    model=agent_settings.deepseek_model,
                    api_key=agent_settings.deepseek_api_key,
                    base_url=agent_settings.deepseek_base_url,
                )
    return _llm


def _get_chain():
    """构建生成链（提示词 + LLM + 输出解析），作为问答图中 generate 节点的执行体。"""
    global _chain
    if _chain is None:
        with _lock:
            if _chain is None:
                _log("正在初始化 LLM 链…")
                # history 占位符在多轮记忆时注入历史消息，单轮问答时为空列表
                prompt = ChatPromptTemplate.from_messages(
                    [
                        ("system", PROMPT_TEMPLATE),
                        MessagesPlaceholder("history", optional=True),
                        ("human", "{question}"),
                    ]
                )
                _chain = prompt | _get_llm() | StrOutputParser()
                _log("LLM 链初始化完成")
    return _chain


def _get_reranker() -> CrossEncoder:
    """加载交叉编码器重排模型（仅 rerank_enabled 时使用）。"""
    global _reranker
    if _reranker is None:
        with _lock:
            if _reranker is None:
                model = agent_settings.rerank_model
                _log(f"正在加载重排模型 {model}（首次加载较慢）…")
                started = time.perf_counter()
                _reranker = CrossEncoder(model, max_length=512)
                _log(f"重排模型加载完成，耗时 {time.perf_counter() - started:.1f}s")
    return _reranker


def _format_docs(docs: list[Document]) -> str:
    return "\n\n".join(f"[{i}] {doc.page_content}" for i, doc in enumerate(docs, 1))


# ---------------------------------------------------------------------------
# 检索侧复用函数：图节点与 retrieve() 共用，保证评测与线上一致
# ---------------------------------------------------------------------------


def _recall_k(top_k: int) -> int:
    """向量召回的候选数量：开启重排时多召回候选，交由交叉编码器精排。"""
    if not agent_settings.rerank_enabled:
        return top_k
    return max(top_k, agent_settings.rerank_recall_k)


def _recall(kb_name: str, question: str, top_k: int) -> list[Document]:
    """向量召回：按知识库取检索实例做相似度检索；查询侧可选加 bge 指令前缀（文档侧不加）。"""
    store = document_service.get_store(kb_name)
    query = BGE_QUERY_INSTRUCTION + question if agent_settings.query_use_instruction else question
    return store.as_retriever(search_kwargs={"k": _recall_k(top_k)}).invoke(query)


def _should_rerank(candidates: list[Document], top_k: int) -> bool:
    """是否需要交叉编码器重排：未开启重排、或候选数未超过 top_k 时重排没有意义。"""
    return agent_settings.rerank_enabled and len(candidates) > top_k


def _rerank(question: str, docs: list[Document]) -> list[Document]:
    """用交叉编码器对候选文档按相关性重排（问题用原文，不加检索指令前缀）。"""
    scores = _get_reranker().predict([(question, doc.page_content) for doc in docs])
    return [doc for _, doc in sorted(zip(scores, docs), key=lambda pair: pair[0], reverse=True)]


def _validate_kb_name(kb_name: str | None) -> str:
    """知识库选择：校验名称是否可用；未指定或不存在时抛 ValueError 并列出可用知识库。"""
    available = document_service.list_kb_names()
    if not available:
        raise ValueError("暂无可用的知识库，请先在文档管理模块创建知识库")
    if kb_name is None:
        raise ValueError(f"未指定知识库，请从以下知识库中选择：{available}")
    if kb_name not in available:
        raise ValueError(f"知识库 {kb_name!r} 不存在，可用知识库：{available}")
    return kb_name


# ---------------------------------------------------------------------------
# 问答图节点（检索 / 重排等均为节点；同步节点由 LangGraph 自动放入线程池执行）
# ---------------------------------------------------------------------------


def _node_resolve_kb(state: RAGState) -> dict:
    """节点：校验知识库名，得到本次问答可用的知识库。"""
    return {"kb_name": _validate_kb_name(state.get("kb_name"))}


def _node_retrieve(state: RAGState) -> dict:
    """节点：向量召回候选；默认以候选作为命中，若走重排节点则由其覆盖。"""
    candidates = _recall(state["kb_name"], state["question"], state["top_k"])
    return {"candidates": candidates, "hits": candidates}


def _node_rerank(state: RAGState) -> dict:
    """节点：交叉编码器精排候选，取前 top_k 作为最终命中。"""
    return {"hits": _rerank(state["question"], state["candidates"])[: state["top_k"]]}


async def _node_generate(state: RAGState) -> dict:
    """节点：以命中资料为上下文调用 LLM 生成回答；无命中资料时明确报错。"""
    hits = state.get("hits") or []
    if not hits:
        raise ValueError(f"知识库 {state['kb_name']} 未检索到相关内容")
    result = await _get_chain().ainvoke(
        {
            "context": _format_docs(hits),
            "question": state["question"],
            "history": state.get("history") or [],
        }
    )
    return {"answer": result}


def _node_finalize(state: RAGState) -> dict:
    """节点：汇总答案来源与命中问答的媒体附件（媒体不参与生成，仅作佐证材料）。"""
    hits = state.get("hits") or []
    sources = list(dict.fromkeys(hit.metadata.get("source", "") for hit in hits))
    qa_ids = [int(hit.metadata["qa_id"]) for hit in hits if str(hit.metadata.get("qa_id", "")).isdigit()]
    return {"sources": sources, "media": document_service.list_media_by_qa_ids(qa_ids)}


def _route_after_retrieve(state: RAGState) -> str:
    """条件边：候选需精排时进入 rerank 节点，否则直接生成。"""
    return "rerank" if _should_rerank(state["candidates"], state["top_k"]) else "generate"


def _get_graph():
    """构建问答状态图的进程级单例，供生产与评测共用。"""
    global _graph
    if _graph is None:
        with _lock:
            if _graph is None:
                _log("正在构建问答图…")
                graph = StateGraph(RAGState)
                graph.add_node("resolve_kb", _node_resolve_kb)
                graph.add_node("retrieve", _node_retrieve)
                graph.add_node("rerank", _node_rerank)
                graph.add_node("generate", _node_generate)
                graph.add_node("finalize", _node_finalize)

                graph.add_edge(START, "resolve_kb")
                graph.add_edge("resolve_kb", "retrieve")
                graph.add_conditional_edges(
                    "retrieve", _route_after_retrieve, ["rerank", "generate"]
                )
                graph.add_edge("rerank", "generate")
                graph.add_edge("generate", "finalize")
                graph.add_edge("finalize", END)

                _graph = graph.compile()
                _log("问答图构建完成")
    return _graph


async def _run_graph(
    question: str,
    kb_name: str | None,
    top_k: int | None = None,
    history: list[BaseMessage] | None = None,
) -> RAGState:
    """执行问答图，返回终态（含答案、命中、来源与媒体）；history 为多轮历史消息。"""
    return await _get_graph().ainvoke(
        {
            "question": question,
            "kb_name": kb_name,
            "top_k": top_k or agent_settings.retrieval_k,
            "history": history or [],
        }
    )


# ---------------------------------------------------------------------------
# 对外入口
# ---------------------------------------------------------------------------


def retrieve(kb_name: str, question: str, k: int | None = None) -> list[Document]:
    """检索层唯一入口：生产问答与评测 harness 共用同一实现。

    所有检索侧优化（查询改写、embedding 查询前缀、混合检索、重排等）都必须在此实现，
    以保证评测分数与线上行为一致（否则优化分数可能是"假优化"）。
    """
    top_k = k or agent_settings.retrieval_k
    candidates = _recall(kb_name, question, top_k)
    if not _should_rerank(candidates, top_k):
        return candidates
    return _rerank(question, candidates)[:top_k]


async def answer_with_context(question: str, kb_name: str | None = None) -> tuple[str, list[Document]]:
    """完整 RAG 问答，返回 (答案, 命中文档)。

    生成层评测需要命中上下文（判定忠实度）时使用；与 answer() 共用同一张问答图。
    """
    final = await _run_graph(question, kb_name)
    return final["answer"], final["hits"]


async def answer(
    question: str,
    kb_name: str | None = None,
    history: list[BaseMessage] | None = None,
) -> tuple[str, list[str], list[dict]]:
    """在指定知识库中检索并生成回答，返回 (答案, 来源列表, 命中问答的媒体附件列表)。

    history 为多轮对话历史（可选）；本函数无状态、不落库，供评测与内部调用。
    """
    final = await _run_graph(question, kb_name, history=history)
    return final["answer"], final["sources"], final["media"]


def _to_messages(history: list[dict]) -> list[BaseMessage]:
    """把会话历史（role/content 字典）转换为 LangChain 消息对象。"""
    return [
        HumanMessage(content=h["content"]) if h["role"] == "user" else AIMessage(content=h["content"])
        for h in history
    ]


async def answer_in_conversation(
    question: str,
    kb_name: str | None,
    conversation_id: str | None,
    user_id: str,
) -> tuple[str, list[str], list[dict], str]:
    """带会话记忆的问答入口，返回 (答案, 来源, 媒体, 会话 id)。

    - 指定 conversation_id：校验归属，以会话绑定的知识库为准，加载最近历史做多轮生成，
      成功后把本轮问答追加到该会话；
    - 未指定：开启新会话，用请求中的知识库做单轮生成，成功后新建会话并写入本轮问答。
    生成失败（知识库无效 / 无命中 / 上游异常）时不落库，避免写入半截会话。

    会话与消息的读写均交由 conversation 模块，且为同步 SQLite 操作，故放入线程池执行。
    """
    history: list[BaseMessage] = []
    if conversation_id is not None:
        conv = await asyncio.to_thread(
            conversation_service.get_conversation, user_id, conversation_id
        )
        kb_name = conv["kb_name"]  # 会话已绑定知识库，以会话为准
        history = _to_messages(
            await asyncio.to_thread(conversation_service.load_history, user_id, conversation_id)
        )

    answer_text, sources, media = await answer(question, kb_name, history=history)

    if conversation_id is None:
        conversation_id = await asyncio.to_thread(
            conversation_service.start_conversation,
            user_id,
            kb_name or "",
            question,
            answer_text,
            sources,
            media,
        )
    else:
        await asyncio.to_thread(
            conversation_service.append_exchange,
            user_id,
            conversation_id,
            question,
            answer_text,
            sources,
            media,
        )
    return answer_text, sources, media, conversation_id