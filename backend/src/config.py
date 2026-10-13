from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.models import UserRecord

# .env 路径锚定到 backend/ 目录，避免依赖进程工作目录
ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,  # 环境变量大小写不敏感
        extra="ignore",  # 各模块配置分散在不同 Settings 中，忽略非本类字段
    )

    # alias 显式声明对应的 .env 变量名
    users: list[UserRecord] = Field(default=[], alias="USERS")

    # 应用业务数据库（文档系统知识库/文档/问答数据），alias 显式声明对应的 .env 变量名
    app_db_path: Path = Field(
        default=Path(__file__).resolve().parents[1] / "data" / "app.db", alias="APP_DB_PATH"
    )


settings = Settings()