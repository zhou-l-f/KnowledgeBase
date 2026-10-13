import { clsx } from "clsx";
import { X } from "lucide-react";
import { useEffect } from "react";
import type { ReactNode } from "react";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  widthClassName?: string;
}

/** 居中弹窗：Esc 关闭、遮罩点击关闭、打开期间锁定页面滚动。 */
export function Modal({
  open,
  onClose,
  title,
  children,
  footer,
  widthClassName = "max-w-lg",
}: ModalProps) {
  useEffect(() => {
    if (!open) return;
    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKey);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handleKey);
      document.body.style.overflow = previousOverflow;
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="animate-fade-in absolute inset-0 bg-ink/35 backdrop-blur-sm" onClick={onClose} />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={clsx(
          "animate-pop-in relative flex max-h-[85vh] w-full flex-col rounded-2xl border border-line bg-paper shadow-[0_36px_80px_-40px_rgba(32,29,24,0.8)]",
          widthClassName,
        )}
      >
        <header className="flex shrink-0 items-center justify-between gap-4 border-b border-line px-5 py-3.5">
          <h2 className="font-display text-lg tracking-wide text-ink">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="关闭"
            className="flex size-8 items-center justify-center rounded-lg text-ink-ghost transition-colors hover:bg-paper-sunk/70 hover:text-ink"
          >
            <X className="size-4" />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>

        {footer ? (
          <footer className="shrink-0 border-t border-line px-5 py-3">{footer}</footer>
        ) : null}
      </div>
    </div>
  );
}
