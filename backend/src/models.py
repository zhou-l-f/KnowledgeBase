from pydantic import BaseModel


class UserRecord(BaseModel):
    """用户身份主数据：user_id 为永久唯一的用户标识。"""

    user_id: str
    password_hash: str