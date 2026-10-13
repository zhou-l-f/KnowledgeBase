from typing import Literal

from pydantic import BaseModel

from src.document.schemas import MediaOut


class MessageOut(BaseModel):
    """会话消息：sources 与 media 为该轮问答的引用来源与佐证材料快照。"""

    id: str
    role: Literal["user", "assistant"]
    content: str
    sources: list[str]
    media: list[MediaOut]
    status: str
    created_at: int


class ConversationOut(BaseModel):
    """会话摘要：列表展示用，不含消息；时间为毫秒时间戳。"""

    id: str
    title: str
    kb_name: str
    created_at: int
    updated_at: int


class ConversationDetailOut(ConversationOut):
    """会话详情：含全部消息（按时间顺序）。"""

    messages: list[MessageOut]