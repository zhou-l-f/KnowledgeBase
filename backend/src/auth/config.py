from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config import ENV_FILE


class AuthSettings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,  # 环境变量大小写不敏感
        extra="ignore",  # 各模块配置分散在不同 Settings 中，忽略非本类字段
    )

    # alias 显式声明对应的 .env 变量名
    jwt_secret_key: str = Field(alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=1440, alias="JWT_EXPIRE_MINUTES")


auth_settings = AuthSettings()