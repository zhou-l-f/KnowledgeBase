import { Database, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { ApiError } from "@/api/client";
import { createKnowledgeBase, deleteKnowledgeBase, updateKnowledgeBase } from "@/api/document";
import type { KnowledgeBase } from "@/api/types";
import { useAuth } from "@/auth/AuthContext";
import { canWrite } from "@/auth/roles";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Drawer } from "@/components/ui/Drawer";
import { Spinner } from "@/components/ui/Spinner";
import { TextArea } from "@/components/ui/TextArea";
import { TextField } from "@/components/ui/TextField";
import { useKnowledgeBases } from "@/document/KnowledgeBaseProvider";

interface KbFormProps {
  initialName: string;
  initialDescription: string;
  submitLabel: string;
  busy: boolean;
  error: string | null;
  onSubmit: (name: string, description: string) => void;
  onCancel: () => void;
}

/** 知识库新建/编辑表单（内联在列表卡片位置）。 */
function KbForm({
  initialName,
  initialDescription,
  submitLabel,
  busy,
  error,
  onSubmit,
  onCancel,
}: KbFormProps) {
  const [name, setName] = useState(initialName);
  const [description, setDescription] = useState(initialDescription);

  return (
    <div className="space-y-3 rounded-xl border border-cinnabar/25 bg-cinnabar/6 p-3.5">
      <TextField
        label="知识库名称"
        autoFocus
        maxLength={64}
        placeholder="例如：公司规章"
        value={name}
        onChange={(e) => setName(e.target.value)}
      />
      <TextArea
        label="描述（可选）"
        rows={2}
        maxLength={255}
        placeholder="简要说明该知识库收录的内容"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
      />
      {error ? <p className="text-xs text-cinnabar">{error}</p> : null}
      <div className="flex justify-end gap-2">
        <Button variant="outline" size="sm" onClick={onCancel} disabled={busy}>
          取消
        </Button>
        <Button
          size="sm"
          loading={busy}
          onClick={() => onSubmit(name.trim(), description.trim())}
        >
          {submitLabel}
        </Button>
      </div>
    </div>
  );
}

/** 知识库管理抽屉：创建 / 编辑 / 删除知识库（写操作仅编辑与管理员可见）。 */
export function KnowledgeBaseDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { kbs, loading, error, reload } = useKnowledgeBases();
  const { user } = useAuth();
  const writable = canWrite(user?.role);

  const [mode, setMode] = useState<"idle" | "create" | "edit">("idle");
  const [editTarget, setEditTarget] = useState<KnowledgeBase | null>(null);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<KnowledgeBase | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  function resetForm() {
    setMode("idle");
    setEditTarget(null);
    setFormError(null);
  }

  async function handleSubmit(name: string, description: string) {
    if (!name) {
      setFormError("知识库名称不能为空");
      return;
    }
    setBusy(true);
    setFormError(null);
    try {
      if (mode === "create") {
        await createKnowledgeBase({ name, description });
      } else if (editTarget) {
        await updateKnowledgeBase(editTarget.name, { name, description });
      }
      await reload();
      resetForm();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "操作失败，请稍后重试");
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    if (!pendingDelete) return;
    setDeleteBusy(true);
    setDeleteError(null);
    try {
      await deleteKnowledgeBase(pendingDelete.name);
      await reload();
      setPendingDelete(null);
      resetForm();
    } catch (err) {
      setDeleteError(err instanceof ApiError ? err.message : "删除失败，请稍后重试");
    } finally {
      setDeleteBusy(false);
    }
  }

  return (
    <>
      <Drawer
        open={open}
        onClose={onClose}
        title="知识库管理"
        subtitle="每个知识库对应一个独立的向量集合，问答时按知识库检索"
      >
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-xs text-ink-ghost">
              共 {kbs.length} 个知识库{writable ? "" : " · 当前角色仅可查看"}
            </p>
            {writable && mode !== "create" ? (
              <Button
                size="sm"
                icon={<Plus className="size-4" />}
                onClick={() => {
                  setMode("create");
                  setEditTarget(null);
                  setFormError(null);
                }}
              >
                新建知识库
              </Button>
            ) : null}
          </div>

          {mode === "create" ? (
            <KbForm
              initialName=""
              initialDescription=""
              submitLabel="创建"
              busy={busy}
              error={formError}
              onSubmit={handleSubmit}
              onCancel={resetForm}
            />
          ) : null}

          {loading ? (
            <div className="flex justify-center py-10">
              <Spinner className="size-5 text-ink-ghost" />
            </div>
          ) : error ? (
            <p className="rounded-lg border border-cinnabar/25 bg-cinnabar/8 px-3 py-2 text-xs text-cinnabar">
              {error}
            </p>
          ) : kbs.length === 0 ? (
            <p className="py-10 text-center text-xs text-ink-ghost">
              暂无知识库{writable ? "，点击右上角「新建知识库」开始" : ""}
            </p>
          ) : (
            <ul className="space-y-2.5">
              {kbs.map((kb) => (
                <li key={kb.id} className="rounded-xl border border-line bg-paper-raised p-3.5">
                  {mode === "edit" && editTarget?.id === kb.id ? (
                    <KbForm
                      initialName={kb.name}
                      initialDescription={kb.description}
                      submitLabel="保存"
                      busy={busy}
                      error={formError}
                      onSubmit={handleSubmit}
                      onCancel={resetForm}
                    />
                  ) : (
                    <>
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex min-w-0 items-start gap-2.5">
                          <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg bg-jade/12 text-jade">
                            <Database className="size-4" strokeWidth={1.9} />
                          </span>
                          <div className="min-w-0">
                            <div className="truncate text-sm font-medium text-ink">{kb.name}</div>
                            <p className="mt-0.5 line-clamp-2 text-xs leading-relaxed text-ink-ghost">
                              {kb.description || "无描述"}
                            </p>
                          </div>
                        </div>
                        <span className="shrink-0 rounded-md bg-paper-sunk px-2 py-0.5 text-[11px] text-ink-faint">
                          {kb.qa_count} 条问答
                        </span>
                      </div>
                      {writable ? (
                        <div className="mt-3 flex gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            icon={<Pencil className="size-3.5" />}
                            onClick={() => {
                              setMode("edit");
                              setEditTarget(kb);
                              setFormError(null);
                            }}
                          >
                            编辑
                          </Button>
                          <Button
                            size="sm"
                            variant="danger"
                            icon={<Trash2 className="size-3.5" />}
                            onClick={() => setPendingDelete(kb)}
                          >
                            删除
                          </Button>
                        </div>
                      ) : null}
                    </>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </Drawer>

      <ConfirmDialog
        open={pendingDelete !== null}
        title="删除知识库"
        message={
          <>
            确定要删除知识库「<span className="text-ink">{pendingDelete?.name}</span>」吗？
            <br />
            该知识库下的全部文档、问答与媒体附件将一并删除，且不可恢复。
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
    </>
  );
}
