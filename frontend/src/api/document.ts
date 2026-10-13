import { http } from "@/api/client";
import type {
  DocumentItem,
  DocumentUploadResult,
  KnowledgeBase,
  KnowledgeBaseCreate,
  KnowledgeBaseUpdate,
  MediaItem,
  QaItem,
  QaWrite,
} from "@/api/types";

// ---------------------------------------------------------------------------
// 知识库
// ---------------------------------------------------------------------------

/** 列出全部知识库及问答总数（需登录）。 */
export function listKnowledgeBases(): Promise<KnowledgeBase[]> {
  return http.get<KnowledgeBase[]>("/document/knowledge-bases");
}

/** 创建知识库并同步建立向量集合（需编辑或管理员）。 */
export function createKnowledgeBase(payload: KnowledgeBaseCreate): Promise<KnowledgeBase> {
  return http.post<KnowledgeBase>("/document/knowledge-bases", payload);
}

/** 修改知识库名称/描述，未填项保持不变（需编辑或管理员）。 */
export function updateKnowledgeBase(
  kbName: string,
  payload: KnowledgeBaseUpdate,
): Promise<KnowledgeBase> {
  return http.put<KnowledgeBase>(
    `/document/knowledge-bases/${encodeURIComponent(kbName)}`,
    payload,
  );
}

/** 删除知识库：数据库记录与向量集合一并删除（需编辑或管理员）。 */
export function deleteKnowledgeBase(kbName: string): Promise<void> {
  return http.del<void>(`/document/knowledge-bases/${encodeURIComponent(kbName)}`);
}

// ---------------------------------------------------------------------------
// 文档
// ---------------------------------------------------------------------------

function documentsPath(kbName: string): string {
  return `/document/knowledge-bases/${encodeURIComponent(kbName)}/documents`;
}

/** 列出知识库下的全部文档。 */
export function listDocuments(kbName: string): Promise<DocumentItem[]> {
  return http.get<DocumentItem[]>(documentsPath(kbName));
}

/** 上传 .txt/.md 文档：解析为问答对入库并写入向量，同名文件覆盖旧数据。 */
export function uploadDocuments(
  kbName: string,
  files: File[],
): Promise<DocumentUploadResult[]> {
  const form = new FormData();
  for (const file of files) {
    form.append("files", file);
  }
  return http.postForm<DocumentUploadResult[]>(documentsPath(kbName), form);
}

/** 删除文档：数据库记录与对应向量一并删除。 */
export function deleteDocument(kbName: string, documentId: number): Promise<void> {
  return http.del<void>(`${documentsPath(kbName)}/${documentId}`);
}

// ---------------------------------------------------------------------------
// 问答
// ---------------------------------------------------------------------------

function qaPath(kbName: string, documentId: number): string {
  return `${documentsPath(kbName)}/${documentId}/qa`;
}

/** 列出指定文档下的全部问答对。 */
export function listQa(kbName: string, documentId: number): Promise<QaItem[]> {
  return http.get<QaItem[]>(qaPath(kbName, documentId));
}

/** 在文档末尾追加一条问答并同步写入向量。 */
export function addQa(kbName: string, documentId: number, payload: QaWrite): Promise<QaItem> {
  return http.post<QaItem>(qaPath(kbName, documentId), payload);
}

/** 修改一条问答并同步重写对应向量索引单元。 */
export function updateQa(
  kbName: string,
  documentId: number,
  qaId: number,
  payload: QaWrite,
): Promise<QaItem> {
  return http.put<QaItem>(`${qaPath(kbName, documentId)}/${qaId}`, payload);
}

/** 删除一条问答：数据库记录与对应向量一并删除。 */
export function deleteQa(kbName: string, documentId: number, qaId: number): Promise<void> {
  return http.del<void>(`${qaPath(kbName, documentId)}/${qaId}`);
}

// ---------------------------------------------------------------------------
// 媒体附件（佐证材料，不参与向量化）
// ---------------------------------------------------------------------------

function mediaPath(kbName: string, documentId: number, qaId: number): string {
  return `${qaPath(kbName, documentId)}/${qaId}/media`;
}

/** 列出指定问答下的全部媒体附件。 */
export function listMedia(
  kbName: string,
  documentId: number,
  qaId: number,
): Promise<MediaItem[]> {
  return http.get<MediaItem[]>(mediaPath(kbName, documentId, qaId));
}

/** 上传媒体附件（图片类）。 */
export function uploadMedia(
  kbName: string,
  documentId: number,
  qaId: number,
  files: File[],
): Promise<MediaItem[]> {
  const form = new FormData();
  for (const file of files) {
    form.append("files", file);
  }
  return http.postForm<MediaItem[]>(mediaPath(kbName, documentId, qaId), form);
}

/** 删除一条媒体附件：数据库记录与磁盘文件一并删除。 */
export function deleteMedia(
  kbName: string,
  documentId: number,
  qaId: number,
  mediaId: number,
): Promise<void> {
  return http.del<void>(`${mediaPath(kbName, documentId, qaId)}/${mediaId}`);
}
