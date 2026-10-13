import { X } from "lucide-react";
import { useEffect, useState } from "react";

import type { MediaItem } from "@/api/types";
import { useAuthedMediaUrl } from "@/chat/useAuthedMediaUrl";
import { Spinner } from "@/components/ui/Spinner";

function Thumbnail({ item, onOpen }: { item: MediaItem; onOpen: () => void }) {
  const { src, status } = useAuthedMediaUrl(item.url);
  return (
    <button
      type="button"
      onClick={onOpen}
      title={item.filename}
      className="group size-24 overflow-hidden rounded-lg border border-line bg-paper-sunk transition-shadow hover:shadow-[0_10px_24px_-14px_rgba(32,29,24,0.6)]"
    >
      {status === "ready" && src ? (
        <img
          src={src}
          alt={item.filename}
          className="size-full object-cover transition-transform duration-300 group-hover:scale-[1.06]"
        />
      ) : status === "loading" ? (
        <span className="flex size-full items-center justify-center text-ink-ghost">
          <Spinner />
        </span>
      ) : (
        <span className="flex size-full items-center justify-center px-1 text-center text-[10px] text-ink-ghost">
          加载失败
        </span>
      )}
    </button>
  );
}

function Lightbox({ item, onClose }: { item: MediaItem; onClose: () => void }) {
  const { src, status } = useAuthedMediaUrl(item.url);

  useEffect(() => {
    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-4 bg-ink/85 p-6 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="max-h-[78vh] overflow-hidden rounded-xl border border-line bg-paper-raised"
        onClick={(event) => event.stopPropagation()}
      >
        {status === "ready" && src ? (
          <img src={src} alt={item.filename} className="max-h-[78vh] w-auto object-contain" />
        ) : (
          <div className="flex size-56 items-center justify-center text-ink-ghost">
            {status === "loading" ? <Spinner className="size-6" /> : "图片加载失败"}
          </div>
        )}
      </div>
      <div className="flex items-center gap-3 text-xs text-paper-raised/75">
        <span className="max-w-[70vw] truncate">{item.filename}</span>
        <button
          type="button"
          onClick={onClose}
          aria-label="关闭"
          className="flex size-7 items-center justify-center rounded-full border border-paper-raised/30 transition-colors hover:bg-paper-raised/15"
        >
          <X className="size-4" />
        </button>
      </div>
    </div>
  );
}

/** 命中问答的媒体附件（佐证材料）：缩略图 + 点击放大查看。 */
export function MediaGallery({ items }: { items: MediaItem[] }) {
  const [openItem, setOpenItem] = useState<MediaItem | null>(null);

  if (items.length === 0) {
    return null;
  }

  return (
    <div>
      <div className="mb-1.5 text-[11px] tracking-wide text-ink-ghost">佐证材料</div>
      <div className="flex flex-wrap gap-2">
        {items.map((item) => (
          <Thumbnail key={item.id} item={item} onOpen={() => setOpenItem(item)} />
        ))}
      </div>
      {openItem ? <Lightbox item={openItem} onClose={() => setOpenItem(null)} /> : null}
    </div>
  );
}
