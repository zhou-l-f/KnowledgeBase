from pydantic import BaseModel, Field


class KnowledgeBaseCreate(BaseModel):
    """创建知识库请求体。"""

    name: str = Field(min_length=1, max_length=64, description="知识库名称（全局唯一）")
    description: str = Field(default="", max_length=255, description="知识库描述")


class KnowledgeBaseUpdate(BaseModel):
    """修改知识库请求体：名称与描述至少填一项，未填项保持不变。"""

    name: str | None = Field(default=None, min_length=1, max_length=64, description="新名称（全局唯一）")
    description: str | None = Field(default=None, max_length=255, description="新描述")


class KnowledgeBaseOut(BaseModel):
    """知识库信息：含问答总数。"""

    id: int
    name: str
    description: str
    qa_count: int


class DocumentOut(BaseModel):
    """文档信息：含问答总数。"""

    id: int
    name: str
    qa_count: int


class QaItemOut(BaseModel):
    """问答对记录。"""

    id: int
    question: str
    answer: str


class QaWrite(BaseModel):
    """新增/修改问答对请求体。"""

    question: str = Field(min_length=1, max_length=2000, description="问题")
    answer: str = Field(min_length=1, max_length=8000, description="答案")


class DocumentUploadOut(BaseModel):
    """单文件上传结果。"""

    document_id: int
    name: str
    qa_count: int
    replaced: bool


class MediaOut(BaseModel):
    """问答对的媒体附件信息。"""

    id: int
    qa_id: int
    filename: str
    mime_type: str
    size: int
    url: str