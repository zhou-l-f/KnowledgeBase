from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config import ENV_FILE


class AgentSettings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,  # 环境变量大小写不敏感
        extra="ignore",  # 各模块配置分散在不同 Settings 中，忽略非本类字段
    )

    # DeepSeek 官方接口（OpenAI 兼容协议），alias 显式声明对应的 .env 变量名
    deepseek_api_key: str = Field(default="", alias="DEEPSEEK_API_KEY")
    deepseek_model: str = Field(default="deepseek-flash", alias="DEEPSEEK_MODEL")
    deepseek_base_url: str = Field(default="https://api.deepseek.com", alias="DEEPSEEK_BASE_URL")

    # 检索参数：每次问答召回并喂给 LLM 的相关片段数。
    # 实测（eval/reports）：开启重排后 k=1/2/4 指标均为 1.000，故取 2——
    # 相比 k=4 上下文减半，同时保留一条冗余降低风险
    retrieval_k: int = Field(default=2, alias="RETRIEVAL_K")

    # bge 系列模型推荐对「查询」加指令前缀；实测 bge-small-zh-v1.5 在本项目语料上
    # 指标零变化（见 eval/reports/q_prefix.json），故默认关闭，保留开关以便复验
    query_use_instruction: bool = Field(default=False, alias="QUERY_USE_INSTRUCTION")

    # 重排（cross-encoder）：先按向量召回 rerank_recall_k 条，再用交叉编码器精排取 top-k。
    # 实测在本项目语料上把 命中率@1 0.978→1.000、MRR 0.985→1.000（见 eval/reports/rerank.json），
    # 代价约 +0.4s/次，故默认开启；可用 RERANK_ENABLED=false 关闭做对照
    rerank_enabled: bool = Field(default=True, alias="RERANK_ENABLED")
    rerank_model: str = Field(
        default=str(Path(__file__).resolve().parents[2] / "models" / "bge-reranker-base"),
        alias="RERANK_MODEL",
    )
    rerank_recall_k: int = Field(default=10, alias="RERANK_RECALL_K")


agent_settings = AgentSettings()