"""认证服务层：用户存储（SQLite）、密码校验、JWT 签发与用户管理。

职责边界：
- 用户数据统一存 SQLite users 表（唯一真源），支持运行时增删改（注册/改角色）；
- .env 中的 USERS 仅作为首次启动种子（users 表为空时导入，全部视为管理员），
  之后完全以数据库为准，不再读取 .env 用户；
- 权限校验（谁能操作什么）由 dependencies.py 中的角色依赖负责，本层不涉及。
"""

import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

import jwt

from src.auth.config import auth_settings
from src.auth.constants import ROLE_ADMIN
from src.auth.exceptions import UserNotFoundError
from src.config import settings
from src.database import get_connection

# PBKDF2 迭代次数，按 OWASP 推荐的强度取值
PBKDF2_ITERATIONS = 600_000


def _log(message: str) -> None:
    print(f"[auth] {message}", flush=True)


# ---------------------------------------------------------------------------
# 启动初始化：建表 + .env 种子导入
# ---------------------------------------------------------------------------


def init() -> None:
    """启动初始化：创建 users 表；表为空时把 .env 的 USERS 作为初始管理员导入。"""
    _init_db()
    _seed_from_env()


def _init_db() -> None:
    """创建 users 表（幂等）。"""
    with get_connection() as con:
        con.executescript(
            """
            create table if not exists users (
                id integer primary key autoincrement,
                user_id text not null unique,
                password_hash text not null,
                role text not null default 'readonly',
                created_at text not null default (datetime('now', 'localtime')),
                updated_at text not null default (datetime('now', 'localtime'))
            );
            """
        )


def _seed_from_env() -> None:
    """.env 的 USERS 仅用于初始化：users 表为空时导入，全部授予管理员角色。"""
    if not settings.users:
        return
    with get_connection() as con:
        if con.execute("select count(*) from users").fetchone()[0] > 0:
            return
        con.executemany(
            "insert into users (user_id, password_hash, role) values (?, ?, ?)",
            [(u.user_id, u.password_hash, ROLE_ADMIN) for u in settings.users],
        )
    _log(f"从 .env 初始化 {len(settings.users)} 个管理员用户（后续以数据库为准）")


# ---------------------------------------------------------------------------
# 密码哈希与校验
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    """生成 pbkdf2_sha256 密码哈希。"""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    """校验密码与哈希是否匹配，采用常数时间比较防止时序攻击。"""
    try:
        algorithm, iterations, salt_hex, digest_hex = password_hash.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        ).hex()
        return hmac.compare_digest(candidate, digest_hex)
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# JWT 令牌
# ---------------------------------------------------------------------------


def create_access_token(user_id: str) -> str:
    """签发 JWT 令牌，sub 中携带用户永久唯一的 user_id。

    角色不写入令牌：每次请求由 get_current_user 从数据库读取，
    使角色变更、用户删除能立即生效，无需等待令牌过期。
    """
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc)
        + timedelta(minutes=auth_settings.jwt_expire_minutes),
    }
    return jwt.encode(
        payload, auth_settings.jwt_secret_key, algorithm=auth_settings.jwt_algorithm
    )


def decode_token(token: str) -> str | None:
    """解析并校验 JWT 令牌，返回其中的 user_id；无效或过期时返回 None。"""
    try:
        payload = jwt.decode(
            token,
            auth_settings.jwt_secret_key,
            algorithms=[auth_settings.jwt_algorithm],
        )
    except jwt.InvalidTokenError:
        return None
    return payload.get("sub")


# ---------------------------------------------------------------------------
# 用户查询与鉴权
# ---------------------------------------------------------------------------


def get_user(user_id: str) -> dict | None:
    """按 user_id 查询用户（含密码哈希与角色），不存在返回 None。"""
    with get_connection() as con:
        row = con.execute(
            "select user_id, password_hash, role from users where user_id = ?", (user_id,)
        ).fetchone()
    return dict(row) if row else None


def authenticate_user(user_id: str, password: str) -> dict | None:
    """校验用户凭证，成功返回 {"user_id", "role"}，失败返回 None。"""
    user = get_user(user_id)
    if user and verify_password(password, user["password_hash"]):
        return {"user_id": user["user_id"], "role": user["role"]}
    return None


# ---------------------------------------------------------------------------
# 用户管理（仅管理员可调用，权限校验在路由依赖层）
# ---------------------------------------------------------------------------


def create_user(user_id: str, password: str, role: str) -> dict:
    """创建用户；user_id 已存在时抛 ValueError。"""
    user_id = user_id.strip()
    if not user_id:
        raise ValueError("用户ID不能为空")
    with get_connection() as con:
        try:
            con.execute(
                "insert into users (user_id, password_hash, role) values (?, ?, ?)",
                (user_id, hash_password(password), role),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"用户 {user_id!r} 已存在") from exc
        row = con.execute(
            "select user_id, role, created_at from users where user_id = ?", (user_id,)
        ).fetchone()
    return dict(row)


def list_users() -> list[dict]:
    """列出全部用户（不含密码哈希）。"""
    with get_connection() as con:
        rows = con.execute(
            "select user_id, role, created_at from users order by id"
        ).fetchall()
    return [dict(r) for r in rows]


def update_user(user_id: str, password: str | None = None, role: str | None = None) -> dict:
    """修改用户密码和/或角色；未提供项保持不变。"""
    if password is None and role is None:
        raise ValueError("未提供任何修改内容（password / role 至少填一项）")
    with get_connection() as con:
        row = con.execute("select id from users where user_id = ?", (user_id,)).fetchone()
        if row is None:
            raise UserNotFoundError(f"用户 {user_id!r} 不存在")
        if password is not None:
            con.execute(
                "update users set password_hash = ?, updated_at = datetime('now', 'localtime') where user_id = ?",
                (hash_password(password), user_id),
            )
        if role is not None:
            con.execute(
                "update users set role = ?, updated_at = datetime('now', 'localtime') where user_id = ?",
                (role, user_id),
            )
        updated = con.execute(
            "select user_id, role, created_at from users where user_id = ?", (user_id,)
        ).fetchone()
    return dict(updated)


def delete_user(user_id: str) -> None:
    """删除用户；不存在时抛 UserNotFoundError。"""
    with get_connection() as con:
        cur = con.execute("delete from users where user_id = ?", (user_id,))
        if cur.rowcount == 0:
            raise UserNotFoundError(f"用户 {user_id!r} 不存在")
