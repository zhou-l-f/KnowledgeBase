"""文档模块配置：本地向量化模型、向量库路径、媒体附件目录。"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config import ENV_FILE


class DocumentSettings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,  # 环境变量大小写不敏感
        extra="ignore",  # 各模块配置分散在不同 Settings 中，忽略非本类字段
    )

    # 本地向量化模型（DeepSeek 不提供 embedding 接口，故用本地 bge 模型），
    # alias 显式声明对应的 .env 变量名
    embedding_model: str = Field(default="BAAI/bge-small-zh-v1.5", alias="EMBEDDING_MODEL")

    # Chroma 向量库存放目录
    chroma_dir: Path = Field(
        default=Path(__file__).resolve().parents[2] / "data" / "chroma", alias="CHROMA_DIR"
    )

    # 媒体附件存放目录：文件按「问答 id / uuid.后缀」落盘，数据库只存元数据与相对路径
    media_root: Path = Field(
        default=Path(__file__).resolve().parents[2] / "data" / "media", alias="MEDIA_ROOT"
    )


document_settings = DocumentSettings()