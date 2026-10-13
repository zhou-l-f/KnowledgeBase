import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status

from src.auth.dependencies import get_current_user
from src.auth.schemas import CurrentUser
from src.conversation import service
from src.conversation.exceptions import ConversationNotFoundError
from src.conversation.schemas import (
    ConversationDetailOut,
    ConversationOut,
)

router = APIRouter(prefix="/conversation", tags=["会话历史"])

# 会话按登录用户隔离：所有接口均需登录，且只能访问本人会话
_User = Annotated[CurrentUser, Depends(get_current_user)]
_ConversationId = Annotated[str, Path(min_length=1, description="会话 id（UUID）")]


@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(user: _User) -> list[ConversationOut]:
    """列出当前登录用户的历史会话（按最近更新倒序）。"""
    items = await asyncio.to_thread(service.list_conversations, user.user_id)
    return [ConversationOut(**item) for item in items]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailOut)
async def get_conversation(conversation_id: _ConversationId, user: _User) -> ConversationDetailOut:
    """获取指定会话的详情（含全部消息）。"""
    try:
        detail = await asyncio.to_thread(service.get_conversation, user.user_id, conversation_id)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ConversationDetailOut(**detail)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(conversation_id: _ConversationId, user: _User) -> None:
    """删除指定会话及其全部消息。"""
    try:
        await asyncio.to_thread(service.delete_conversation, user.user_id, conversation_id)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc