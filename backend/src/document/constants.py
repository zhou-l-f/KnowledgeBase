"""文档模块常量。"""

# 支持上传/导入的文件后缀（统一按 Q:/A: 文本格式解析）
SUPPORTED_SUFFIXES = (".txt", ".md")

# 问答对支持的媒体附件后缀（图片类，按需扩展）
MEDIA_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")

# 单个媒体文件大小上限（字节）
MAX_MEDIA_SIZE_BYTES = 10 * 1024 * 1024

# 向量集合元数据中的结构标记：用于识别旧版索引结构，触发一次性从数据库重建
INDEX_SCHEMA_META_KEY = "index_schema"
INDEX_SCHEMA = "v1"