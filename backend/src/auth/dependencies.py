"""认证模块路由依赖：令牌解析、当前用户与角色鉴权。

权限模型（角色由低到高：readonly < editor < admin）：
- get_current_user：任意已登录用户，返回 CurrentUser（含角色）；
- require_editor：内容写权限（admin / editor），用于知识库/文档/问答/媒体的增删改；
- require_admin：管理员，用于用户管理等特权操作。

角色不存于令牌，而是每次请求查库获得，因此角色变更/用户删除立即生效。
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from src.auth.constants import CONTENT_WRITE_ROLES, ROLE_ADMIN
from src.auth.schemas import CurrentUser
from src.auth import service as auth_service

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> CurrentUser:
    """解析 JWT 并查出当前用户（含角色）。

    无令牌、令牌无效，或用户已被删除时返回 401，前端据此跳转回登录页。
    """
    user_id = auth_service.decode_token(token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌无效或已过期，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = auth_service.get_user(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被删除，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return CurrentUser(user_id=user["user_id"], role=user["role"])


def require_editor(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    """要求内容写权限（admin / editor），否则 403。"""
    if user.role not in CONTENT_WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="当前角色无写权限，需要编辑或管理员角色",
        )
    return user


def require_admin(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    """要求管理员角色，否则 403。"""
    if user.role != ROLE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="该操作仅管理员可执行",
        )
    return user
