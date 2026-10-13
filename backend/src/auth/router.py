from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from src.auth.dependencies import get_current_user, require_admin
from src.auth.exceptions import UserNotFoundError
from src.auth.schemas import (
    CurrentUser,
    LoginRequest,
    TokenResponse,
    UserCreate,
    UserOut,
    UserUpdate,
)
from src.auth.service import (
    authenticate_user,
    create_access_token,
    create_user,
    delete_user,
    list_users,
    update_user,
)

router = APIRouter(prefix="/auth", tags=["认证"])

# 任意已登录用户 / 仅管理员
_User = Annotated[CurrentUser, Depends(get_current_user)]
_Admin = Annotated[CurrentUser, Depends(require_admin)]


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    user = authenticate_user(payload.user_id, payload.password)
    if user is None:
        # 不区分用户不存在还是密码错误，避免用户枚举
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户ID或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(access_token=create_access_token(user["user_id"]))


@router.get("/me", response_model=CurrentUser)
def read_me(user: _User) -> CurrentUser:
    """获取当前登录用户信息（含角色），供前端控制界面显隐。"""
    return user


# ---------------------------------------------------------------------------
# 用户管理：仅管理员可执行
# ---------------------------------------------------------------------------


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_new_user(payload: UserCreate, admin: _Admin) -> UserOut:
    """创建用户（注册）：仅管理员可调用，可指定初始角色。"""
    try:
        created = create_user(payload.user_id, payload.password, payload.role)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return UserOut(**created)


@router.get("/users", response_model=list[UserOut])
def list_all_users(admin: _Admin) -> list[UserOut]:
    """列出全部用户（需管理员）。"""
    return [UserOut(**user) for user in list_users()]


@router.put("/users/{user_id}", response_model=UserOut)
def update_existing_user(user_id: str, payload: UserUpdate, admin: _Admin) -> UserOut:
    """修改用户的密码/角色（需管理员）；不允许修改自己的角色，避免误锁权限。"""
    if user_id == admin.user_id and payload.role is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能修改自己的角色，请让其他管理员操作",
        )
    try:
        updated = update_user(user_id, payload.password, payload.role)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return UserOut(**updated)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_user(user_id: str, admin: _Admin) -> None:
    """删除用户（需管理员）；不允许删除自己，避免误锁权限。"""
    if user_id == admin.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己",
        )
    try:
        delete_user(user_id)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
