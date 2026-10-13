import { ArrowLeft, ImagePlus, Pencil, Plus, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { addQa, deleteQa, listQa, updateQa } from "@/api/document";
import type { DocumentItem, QaItem } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { MediaPanel } from "@/document/MediaPanel";
import { Spinner } from "@/components/ui/Spinner";
import { TextArea } from "@/components/ui/TextArea";

interface QaFormProps {
  initialQuestion: string;
  initialAnswer: string;
  submitLabel: string;
  busy: boolean;
  error: string | null;
  onSubmit: (question: string, answer: string) => void;
  onCancel: () => void;
}

function QaForm({
  initialQuestion,
  initialAnswer,
  submitLabel,
  busy,
  error,
  onSubmit,
  onCancel,
}: QaFormProps) {
  const [question, setQuestion] = useState(initialQuestion);
  const [answer, setAnswer] = useState(initialAnswer);

  return (
    <div className="space-y-3 rounded-xl border border-cinnabar/25 bg-cinnabar/6 p-3.5">
      <TextArea
        label="问题"
        rows={2}
        autoFocus
        maxLength={2000}
        placeholder="请输入问题"
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
      />
      <TextArea
        label="答案"
        rows={4}
        maxLength={8000}
        placeholder="请输入答案"
        value={answer}
        onChange={(e) => setAnswer(e.target.value)}
      />
      {error ? <p className="text-xs text-cinnabar">{error}</p> : null}
      <div className="flex justify-end gap-2">
        <Button variant="outline" size="sm" onClick={onCancel} disabled={busy}>
          取消
        </Button>
        <Button
          size="sm"
          loading={busy}
          onClick={() => onSubmit(question.trim(), answer.trim())}
        >
          {submitLabel}
        </Button>
      </div>
    </div>
  );
}

interface QaListPanelProps {
  kbName: string;
  document: DocumentItem;
  writable: boolean;
  onBack: () => void;
  onChanged: () => Promise<void>;
}

/** 文档下的问答管理：列表 + 新增 / 修改 / 删除 + 佐证材料。 */
export function QaListPanel({ kbName, document, writable, onBack, onChanged }: QaListPanelProps) {
  const [items, setItems] = useState<QaItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [mode, setMode] = useState<"idle" | "create" | "edit">("idle");
  const [editTarget, setEditTarget] = useState<QaItem | null>(null);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [mediaOpenId, setMediaOpenId] = useState<number | null>(null);
  const [pendingDelete, setPendingDelete] = useState<QaItem | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setItems(await listQa(kbName, document.id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "问答列表加载失败");
    } finally {
      setLoading(false);
    }
  }, [kbName, document.id]);

  useEffect(() => {
    void load();
  }, [load]);

  function resetForm() {
    setMode("idle");
    setEditTarget(null);
    setFormError(null);
  }

  async function handleSubmit(question: string, answer: string) {
    if (!question || !answer) {
      setFormError("问题与答案均不能为空");
      return;
    }
    setBusy(true);
    setFormError(null);
    try {
      if (mode === "create") {
        await addQa(kbName, document.id, { question, answer });
      } else if (editTarget) {
        await updateQa(kbName, document.id, editTarget.id, { question, answer });
      }
      await load();
      await onChanged();
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
      await deleteQa(kbName, document.id, pendingDelete.id);
      await load();
      await onChanged();
      setPendingDelete(null);
      resetForm();
    } catch (err) {
      setDeleteError(err instanceof ApiError ? err.message : "删除失败，请稍后重试");
    } finally {
      setDeleteBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onBack}
          className="flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-ink-faint transition-colors hover:bg-paper-sunk/60 hover:text-ink"
        >
          <ArrowLeft className="size-3.5" />
          返回文档列表
        </button>
      </div>

      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium text-ink">{document.name}</div>
          <div className="text-[11px] text-ink-ghost">共 {items.length} 条问答</div>
        </div>
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
            新增问答
          </Button>
        ) : null}
      </div>

      {mode === "create" ? (
        <QaForm
          initialQuestion=""
          initialAnswer=""
          submitLabel="添加"
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
      ) : items.length === 0 ? (
        <p className="py-10 text-center text-xs text-ink-ghost">该文档暂无问答</p>
      ) : (
        <ul className="space-y-2.5">
          {items.map((item) => (
            <li key={item.id} className="rounded-xl border border-line bg-paper-raised p-3.5">
              {mode === "edit" && editTarget?.id === item.id ? (
                <QaForm
                  initialQuestion={item.question}
                  initialAnswer={item.answer}
                  submitLabel="保存"
                  busy={busy}
                  error={formError}
                  onSubmit={handleSubmit}
                  onCancel={resetForm}
                />
              ) : (
                <>
                  <div className="flex items-start gap-2">
                    <span className="mt-0.5 shrink-0 rounded bg-cinnabar/12 px-1.5 py-0.5 text-[11px] font-medium text-cinnabar">
                      Q
                    </span>
                    <p className="text-sm leading-relaxed text-ink">{item.question}</p>
                  </div>
                  <div className="mt-2 flex items-start gap-2">
                    <span className="mt-0.5 shrink-0 rounded bg-jade/12 px-1.5 py-0.5 text-[11px] font-medium text-jade">
                      A
                    </span>
                    <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink-soft">
                      {item.answer}
                    </p>
                  </div>

                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      icon={<ImagePlus className="size-3.5" />}
                      onClick={() => setMediaOpenId(mediaOpenId === item.id ? null : item.id)}
                    >
                      {mediaOpenId === item.id ? "收起材料" : "佐证材料"}
                    </Button>
                    {writable ? (
                      <>
                        <Button
                          size="sm"
                          variant="outline"
                          icon={<Pencil className="size-3.5" />}
                          onClick={() => {
                            setMode("edit");
                            setEditTarget(item);
                            setFormError(null);
                          }}
                        >
                          编辑
                        </Button>
                        <Button
                          size="sm"
                          variant="danger"
                          icon={<Trash2 className="size-3.5" />}
                          onClick={() => setPendingDelete(item)}
                        >
                          删除
                        </Button>
                      </>
                    ) : null}
                  </div>

                  {mediaOpenId === item.id ? (
                    <MediaPanel
                      kbName={kbName}
                      documentId={document.id}
                      qaId={item.id}
                      writable={writable}
                    />
                  ) : null}
                </>
              )}
            </li>
          ))}
        </ul>
      )}

      <ConfirmDialog
        open={pendingDelete !== null}
        title="删除问答"
        message={
          <>
            确定要删除这条问答吗？删除后该问答的向量索引与佐证材料将一并移除。
            {pendingDelete ? (
              <span className="mt-2 block text-xs text-ink-ghost">「{pendingDelete.question}」</span>
            ) : null}
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
