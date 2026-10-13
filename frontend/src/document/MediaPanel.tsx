import { ImagePlus, Trash2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "@/api/client";
import { deleteMedia, listMedia, uploadMedia } from "@/api/document";
import type { MediaItem } from "@/api/types";
import { useAuthedMediaUrl } from "@/chat/useAuthedMediaUrl";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";

const ACCEPT = ".png,.jpg,.jpeg,.gif,.webp,.bmp";

function MediaThumb({
  item,
  busy,
  onDelete,
}: {
  item: MediaItem;
  busy: boolean;
  onDelete: () => void;
}) {
  const { src, status } = useAuthedMediaUrl(item.url);

  return (
    <div className="group relative size-20 overflow-hidden rounded-lg border border-line bg-paper-sunk">
      {status === "ready" && src ? (
        <img src={src} alt={item.filename} className="size-full object-cover" />
      ) : (
        <span className="flex size-full items-center justify-center text-ink-ghost">
          {status === "loading" ? <Spinner /> : "加载失败"}
        </span>
      )}
      <button
        type="button"
        onClick={onDelete}
        disabled={busy}
        aria-label={`删除 ${item.filename}`}
        className="absolute right-1 top-1 flex size-6 items-center justify-center rounded-md bg-ink/70 text-paper opacity-70 transition-all hover:bg-cinnabar hover:opacity-100 disabled:opacity-30"
      >
        <Trash2 className="size-3.5" />
      </button>
      <span className="absolute inset-x-0 bottom-0 truncate bg-ink/60 px-1 py-0.5 text-[10px] text-paper opacity-0 transition-opacity group-hover:opacity-100">
        {item.filename}
      </span>
    </div>
  );
}

interface MediaPanelProps {
  kbName: string;
  documentId: number;
  qaId: number;
  writable: boolean;
}

/** 单条问答的佐证材料管理：缩略图 + 上传 + 删除。 */
export function MediaPanel({ kbName, documentId, qaId, writable }: MediaPanelProps) {
  const [items, setItems] = useState<MediaItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setItems(await listMedia(kbName, documentId, qaId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "佐证材料加载失败");
    } finally {
      setLoading(false);
    }
  }, [kbName, documentId, qaId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      await uploadMedia(kbName, documentId, qaId, Array.from(files));
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "上传失败，请稍后重试");
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function handleDelete(mediaId: number) {
    setBusy(true);
    setError(null);
    try {
      await deleteMedia(kbName, documentId, qaId, mediaId);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "删除失败，请稍后重试");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-3 rounded-lg border border-line bg-paper-sunk/40 p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="text-[11px] tracking-wide text-ink-ghost">佐证材料（不参与向量检索）</span>
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
              variant="outline"
              icon={<ImagePlus className="size-3.5" />}
              loading={busy}
              onClick={() => inputRef.current?.click()}
            >
              上传图片
            </Button>
          </>
        ) : null}
      </div>

      {error ? <p className="mb-2 text-xs text-cinnabar">{error}</p> : null}

      {loading ? (
        <div className="flex justify-center py-3">
          <Spinner className="size-4 text-ink-ghost" />
        </div>
      ) : items.length === 0 ? (
        <p className="py-2 text-center text-xs text-ink-ghost">暂无佐证材料</p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {items.map((item) => (
            <MediaThumb
              key={item.id}
              item={item}
              busy={busy}
              onDelete={() => void handleDelete(item.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
