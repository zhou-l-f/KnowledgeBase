from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from src.agent.schemas import InvokeRequest, InvokeResponse
from src.agent.service import answer_in_conversation
from src.auth.dependencies import get_current_user
from src.auth.schemas import CurrentUser
from src.conversation.exceptions import ConversationNotFoundError

router = APIRouter(prefix="/agent", tags=["大模型"])

# RAG 问答：任意已登录用户均可调用（只读操作）
_User = Annotated[CurrentUser, Depends(get_current_user)]


@router.post("/invoke", response_model=InvokeResponse)
async def invoke(payload: InvokeRequest, user: _User) -> InvokeResponse:
    """RAG 问答：在指定知识库中检索并调用 DeepSeek 生成回答（需登录）。

    带 conversation_id 时续聊该会话（以会话绑定知识库为准，注入最近历史做多轮生成）；
    不带则开启新会话。两种情况的问答都会落库并由后端全权负责记忆存储。
    """
    try:
        answer_text, sources, media, conversation_id = await answer_in_conversation(
            payload.question, payload.kb_name, payload.conversation_id, user.user_id
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        # 业务性失败（知识库不存在 / 未配置 API Key / 未检索到内容）返回 400，提示信息可操作
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        # 上游服务（LLM / 向量库）调用失败
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"模型服务调用失败：{exc}") from exc
    return InvokeResponse(
        answer=answer_text, sources=sources, media=media, conversation_id=conversation_id
    )