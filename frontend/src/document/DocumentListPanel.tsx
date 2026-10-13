import { FileText, Trash2, Upload } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "@/api/client";
import { deleteDocument, listDocuments, uploadDocuments } from "@/api/document";
import type { DocumentItem } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Spinner } from "@/components/ui/Spinner";

const ACCEPT = ".txt,.md";

interface DocumentListPanelProps {
  kbName: string;
  writable: boolean;
  onOpen: (doc: DocumentItem) => void;
  onChanged: () => Promise<void>;
}

/** 知识库下的文档管理：列表 + 上传 + 删除，可下钻到问答管理。 */
export function DocumentListPanel({
  kbName,
  writable,
  onOpen,
  onChanged,
}: DocumentListPanelProps) {
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<DocumentItem | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setDocs(await listDocuments(kbName));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "文档列表加载失败");
    } finally {
      setLoading(false);
    }
  }, [kbName]);

  useEffect(() => {
    setNotice(null);
    void load();
  }, [load]);

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    setUploading(true);
    setNotice(null);
    setError(null);
    try {
      const results = await uploadDocuments(kbName, Array.from(files));
      const summary = results
        .map((r) => `${r.name}（${r.qa_count} 条问答${r.replaced ? "，已覆盖同名文档" : ""}）`)
        .join("；");
      setNotice(`上传成功：${summary}`);
      await load();
      await onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "上传失败，请稍后重试");
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function handleDelete() {
    if (!pendingDelete) return;
    setDeleteBusy(true);
    setDeleteError(null);
    try {
      await deleteDocument(kbName, pendingDelete.id);
      await load();
      await onChanged();
      setPendingDelete(null);
    } catch (err) {
      setDeleteError(err instanceof ApiError ? err.message : "删除失败，请稍后重试");
    } finally {
      setDeleteBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs leading-relaxed text-ink-ghost">
          共 {docs.length} 个文档 · 支持 .txt/.md（按 Q:/A: 格式解析，同名覆盖）
        </p>
        {writable ? (
          <>
            <input
              ref={inputRef}
              type="file"
              accept={ACCEPT}
              multiple
              className="hidden"
              onChange={(e) => void handleFiles(e.target.files)}
            />
            <Button
              size="sm"
              icon={<Upload className="size-4" />}
              loading={uploading}
              onClick={() => inputRef.current?.click()}
            >
              上传文档
            </Button>
          </>
        ) : null}
      </div>

      {notice ? (
        <p className="rounded-lg border border-jade/25 bg-jade/8 px-3 py-2 text-xs text-jade">
          {notice}
        </p>
      ) : null}
      {error ? (
        <p className="rounded-lg border border-cinnabar/25 bg-cinnabar/8 px-3 py-2 text-xs text-cinnabar">
          {error}
        </p>
      ) : null}

      {loading ? (
        <div className="flex justify-center py-10">
          <Spinner className="size-5 text-ink-ghost" />
        </div>
      ) : docs.length === 0 ? (
        <p className="py-10 text-center text-xs text-ink-ghost">
          该知识库暂无文档{writable ? "，点击右上角「上传文档」添加" : ""}
        </p>
      ) : (
        <ul className="space-y-2.5">
          {docs.map((doc) => (
            <li key={doc.id} className="rounded-xl border border-line bg-paper-raised p-3.5">
              <div className="flex items-start justify-between gap-3">
                <div className="flex min-w-0 items-start gap-2.5">
                  <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg bg-jade/12 text-jade">
                    <FileText className="size-4" strokeWidth={1.9} />
                  </span>
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium text-ink">{doc.name}</div>
                    <div className="mt-0.5 text-[11px] text-ink-ghost">{doc.qa_count} 条问答</div>
                  </div>
                </div>
                <div className="flex shrink-0 gap-2">
                  <Button size="sm" variant="outline" onClick={() => onOpen(doc)}>
                    查看问答
                  </Button>
                  {writable ? (
                    <Button
                      size="sm"
                      variant="danger"
                      icon={<Trash2 className="size-3.5" />}
                      onClick={() => setPendingDelete(doc)}
                    >
                      删除
                    </Button>
                  ) : null}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}

      <ConfirmDialog
        open={pendingDelete !== null}
        title="删除文档"
        message={
          <>
            确定要删除文档「<span className="text-ink">{pendingDelete?.name}</span>」吗？
            <br />
            该文档下的全部问答、向量索引与佐证材料将一并删除，且不可恢复。
          </>
        }
        confirmText="删除"
        danger
        loading={deleteBusy}
        error={deleteError}
        onConfirm={handleDelete}
        onCancel={() => {
          setPendingDelete(null);
          setDeleteError(null);
        }}
      />
    </div>
  );
}
