from pydantic import BaseModel, Field

from src.document.schemas import MediaOut


class InvokeRequest(BaseModel):
    """问答请求体：问题文本、目标知识库与可选会话 id（用于多轮续聊）。"""

    question: str = Field(min_length=1, max_length=2000, description="向知识库提出的问题")
    kb_name: str | None = Field(
        default=None,
        max_length=64,
        description="目标知识库名称；开启新会话时必填，续聊时以会话绑定的知识库为准",
    )
    conversation_id: str | None = Field(
        default=None, max_length=64, description="续聊的会话 id；不填则开启新会话"
    )


class InvokeResponse(BaseModel):
    """问答结果：模型回答、引用来源、命中问答的媒体附件与所属会话 id。"""

    answer: str
    sources: list[str]
    media: list[MediaOut] = Field(default_factory=list)
    conversation_id: str = Field(description="本轮问答所属会话 id（新建或续聊）")