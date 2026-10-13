from pydantic import BaseModel, Field, field_validator

from src.auth.constants import ALL_ROLES, ROLE_READONLY


def _ensure_valid_role(value: str | None) -> str | None:
    """校验角色取值是否合法（None 表示不修改，放行）。"""
    if value is not None and value not in ALL_ROLES:
        raise ValueError(f"角色 {value!r} 不合法，可选值：{'、'.join(ALL_ROLES)}")
    return value


class LoginRequest(BaseModel):
    """登录请求体：仅用户ID与密码。"""

    user_id: str = Field(min_length=1, max_length=64, description="用户唯一ID")
    password: str = Field(min_length=1, max_length=128, description="登录密码")


class TokenResponse(BaseModel):
    """登录成功后返回的 JWT 令牌。"""

    access_token: str
    token_type: str = "bearer"


class CurrentUser(BaseModel):
    """当前登录用户：由令牌解析并查库得到，含角色供鉴权使用。"""

    user_id: str
    role: str


class UserCreate(BaseModel):
    """管理员创建用户请求体。"""

    user_id: str = Field(min_length=1, max_length=64, description="用户唯一ID")
    password: str = Field(min_length=6, max_length=128, description="初始密码（至少 6 位）")
    role: str = Field(default=ROLE_READONLY, description="角色：admin / editor / readonly")

    _check_role = field_validator("role")(_ensure_valid_role)


class UserUpdate(BaseModel):
    """管理员修改用户请求体：密码与角色至少填一项，未填项保持不变。"""

    password: str | None = Field(default=None, min_length=6, max_length=128, description="重置密码")
    role: str | None = Field(default=None, description="新角色：admin / editor / readonly")

    _check_role = field_validator("role")(_ensure_valid_role)


class UserOut(BaseModel):
    """用户信息：不含密码哈希。"""

    user_id: str
    role: str
    created_at: str
