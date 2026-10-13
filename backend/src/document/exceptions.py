"""文档模块自定义异常：路由层据此映射为 404。"""


class KnowledgeBaseNotFoundError(Exception):
    """知识库不存在。"""


class DocumentNotFoundError(Exception):
    """文档不存在。"""


class QaItemNotFoundError(Exception):
    """问答记录不存在。"""


class MediaNotFoundError(Exception):
    """媒体附件不存在。"""