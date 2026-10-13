import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Path, UploadFile, status
from fastapi.responses import FileResponse

from src.auth.dependencies import get_current_user, require_editor
from src.auth.schemas import CurrentUser
from src.document import service
from src.document.exceptions import (
    DocumentNotFoundError,
    KnowledgeBaseNotFoundError,
    MediaNotFoundError,
    QaItemNotFoundError,
)
from src.document.schemas import (
    DocumentOut,
    DocumentUploadOut,
    KnowledgeBaseCreate,
    KnowledgeBaseOut,
    KnowledgeBaseUpdate,
    MediaOut,
    QaItemOut,
    QaWrite,
)

router = APIRouter(prefix="/document", tags=["文档管理"])

# 读接口：任意已登录用户；写接口：编辑或管理员（admin / editor）
_User = Annotated[CurrentUser, Depends(get_current_user)]
_Editor = Annotated[CurrentUser, Depends(require_editor)]


# ---------------------------------------------------------------------------
# 知识库：创建 / 列表 / 修改 / 删除
# ---------------------------------------------------------------------------


@router.post("/knowledge-bases", response_model=KnowledgeBaseOut, status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(payload: KnowledgeBaseCreate, user: _Editor) -> KnowledgeBaseOut:
    """创建知识库：落库并同步建立对应的向量集合（需编辑或管理员）。"""
    try:
        kb = await asyncio.to_thread(service.create_kb, payload.name, payload.description)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return KnowledgeBaseOut(**kb)


@router.get("/knowledge-bases", response_model=list[KnowledgeBaseOut])
async def list_knowledge_bases(user: _User) -> list[KnowledgeBaseOut]:
    """列出全部知识库及问答总数（需登录）。"""
    kbs = await asyncio.to_thread(service.list_kbs)
    return [KnowledgeBaseOut(**kb) for kb in kbs]


@router.put("/knowledge-bases/{kb_name}", response_model=KnowledgeBaseOut)
async def update_knowledge_base(
    kb_name: str, payload: KnowledgeBaseUpdate, user: _Editor
) -> KnowledgeBaseOut:
    """修改知识库名称/描述，未填项保持不变；改名会按新名称重建向量集合（需编辑或管理员）。"""
    try:
        kb = await asyncio.to_thread(service.update_kb, kb_name, payload.name, payload.description)
    except KnowledgeBaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return KnowledgeBaseOut(**kb)


@router.delete("/knowledge-bases/{kb_name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_base(kb_name: str, user: _Editor) -> None:
    """删除知识库：数据库记录与向量集合一并删除（需编辑或管理员）。"""
    try:
        await asyncio.to_thread(service.delete_kb, kb_name)
    except KnowledgeBaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# 文档：上传 / 列表 / 删除（挂在知识库之下）
# ---------------------------------------------------------------------------


@router.post(
    "/knowledge-bases/{kb_name}/documents",
    response_model=list[DocumentUploadOut],
    status_code=status.HTTP_201_CREATED,
)
async def upload_documents(
    kb_name: str,
    user: _Editor,
    files: Annotated[list[UploadFile], File(description="要上传的 .txt/.md Q/A 文档")],
) -> list[DocumentUploadOut]:
    """上传文档：解析为问答对 -> 存入数据库 -> 写入向量集合（需编辑或管理员）。同名文件覆盖旧数据。"""
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请至少上传一个文件")
    results: list[DocumentUploadOut] = []
    for file in files:
        content = await file.read()
        try:
            info = await asyncio.to_thread(service.save_upload, kb_name, file.filename or "", content)
        except KnowledgeBaseNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        results.append(DocumentUploadOut(**info))
    return results


@router.get("/knowledge-bases/{kb_name}/documents", response_model=list[DocumentOut])
async def list_documents(kb_name: str, user: _User) -> list[DocumentOut]:
    """列出知识库下的全部文档（需登录）。"""
    try:
        docs = await asyncio.to_thread(service.list_documents, kb_name)
    except KnowledgeBaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [DocumentOut(**doc) for doc in docs]


@router.delete(
    "/knowledge-bases/{kb_name}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_document(
    kb_name: str, document_id: Annotated[int, Path(gt=0)], user: _Editor
) -> None:
    """删除知识库下的指定文档：数据库记录与对应向量一并删除（需编辑或管理员）。"""
    try:
        await asyncio.to_thread(service.delete_document, kb_name, document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# 问答：列表 / 新增 / 修改 / 删除（挂在知识库的文档之下）
# ---------------------------------------------------------------------------


@router.get(
    "/knowledge-bases/{kb_name}/documents/{document_id}/qa",
    response_model=list[QaItemOut],
)
async def list_qa(
    kb_name: str, document_id: Annotated[int, Path(gt=0)], user: _User
) -> list[QaItemOut]:
    """列出指定文档下的全部问答对（需登录）。"""
    try:
        items = await asyncio.to_thread(service.list_qa, kb_name, document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [QaItemOut(**item) for item in items]


@router.post(
    "/knowledge-bases/{kb_name}/documents/{document_id}/qa",
    response_model=QaItemOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_qa(
    kb_name: str,
    document_id: Annotated[int, Path(gt=0)],
    payload: QaWrite,
    user: _Editor,
) -> QaItemOut:
    """在指定文档末尾追加一条问答并同步写入向量（需编辑或管理员）。"""
    try:
        item = await asyncio.to_thread(
            service.add_qa, kb_name, document_id, payload.question, payload.answer
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return QaItemOut(**item)


@router.put(
    "/knowledge-bases/{kb_name}/documents/{document_id}/qa/{qa_id}",
    response_model=QaItemOut,
)
async def update_qa(
    kb_name: str,
    document_id: Annotated[int, Path(gt=0)],
    qa_id: Annotated[int, Path(gt=0)],
    payload: QaWrite,
    user: _Editor,
) -> QaItemOut:
    """修改一条问答：更新数据库并同步重写对应向量索引单元（需编辑或管理员）。"""
    try:
        item = await asyncio.to_thread(
            service.update_qa, kb_name, document_id, qa_id, payload.question, payload.answer
        )
    except QaItemNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return QaItemOut(**item)


@router.delete(
    "/knowledge-bases/{kb_name}/documents/{document_id}/qa/{qa_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_qa(
    kb_name: str,
    document_id: Annotated[int, Path(gt=0)],
    qa_id: Annotated[int, Path(gt=0)],
    user: _Editor,
) -> None:
    """删除一条问答：数据库记录与对应向量一并删除（需编辑或管理员）。"""
    try:
        await asyncio.to_thread(service.delete_qa, kb_name, document_id, qa_id)
    except QaItemNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# 媒体附件：上传 / 列表 / 内容 / 删除（挂在问答之下，仅作佐证材料，不参与向量化）
# ---------------------------------------------------------------------------


@router.get(
    "/knowledge-bases/{kb_name}/documents/{document_id}/qa/{qa_id}/media",
    response_model=list[MediaOut],
)
async def list_media(
    kb_name: str,
    document_id: Annotated[int, Path(gt=0)],
    qa_id: Annotated[int, Path(gt=0)],
    user: _User,
) -> list[MediaOut]:
    """列出指定问答下的全部媒体附件（需登录）。"""
    try:
        items = await asyncio.to_thread(service.list_media, kb_name, document_id, qa_id)
    except QaItemNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [MediaOut(**item) for item in items]


@router.post(
    "/knowledge-bases/{kb_name}/documents/{document_id}/qa/{qa_id}/media",
    response_model=list[MediaOut],
    status_code=status.HTTP_201_CREATED,
)
async def upload_media(
    kb_name: str,
    document_id: Annotated[int, Path(gt=0)],
    qa_id: Annotated[int, Path(gt=0)],
    user: _Editor,
    files: Annotated[list[UploadFile], File(description="要上传的媒体文件（图片类）")],
) -> list[MediaOut]:
    """给指定问答上传媒体附件：文件落盘 + 数据库记录元数据（需编辑或管理员）。"""
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请至少上传一个文件")
    results: list[MediaOut] = []
    for file in files:
        content = await file.read()
        try:
            info = await asyncio.to_thread(
                service.save_media,
                kb_name,
                document_id,
                qa_id,
                file.filename or "",
                content,
                file.content_type or "",
            )
        except QaItemNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        results.append(MediaOut(**info))
    return results


@router.get(
    "/knowledge-bases/{kb_name}/documents/{document_id}/qa/{qa_id}/media/{media_id}/content",
)
async def get_media_content(
    kb_name: str,
    document_id: Annotated[int, Path(gt=0)],
    qa_id: Annotated[int, Path(gt=0)],
    media_id: Annotated[int, Path(gt=0)],
    user: _User,
) -> FileResponse:
    """返回媒体文件内容（需登录，浏览器可带令牌直接展示）。"""
    try:
        info = await asyncio.to_thread(service.get_media, kb_name, document_id, qa_id, media_id)
    except MediaNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return FileResponse(
        info["path"],
        media_type=info["mime_type"],
        filename=info["filename"],
        content_disposition_type="inline",
    )


@router.delete(
    "/knowledge-bases/{kb_name}/documents/{document_id}/qa/{qa_id}/media/{media_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_media(
    kb_name: str,
    document_id: Annotated[int, Path(gt=0)],
    qa_id: Annotated[int, Path(gt=0)],
    media_id: Annotated[int, Path(gt=0)],
    user: _Editor,
) -> None:
    """删除一条媒体附件：数据库记录与磁盘文件一并删除（需编辑或管理员）。"""
    try:
        await asyncio.to_thread(service.delete_media, kb_name, document_id, qa_id, media_id)
    except MediaNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
