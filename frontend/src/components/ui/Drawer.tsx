import { clsx } from "clsx";
import { X } from "lucide-react";
import { useEffect } from "react";
import type { ReactNode } from "react";

interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
  /** 面板宽度类名，默认适配中等宽度表单内容 */
  widthClassName?: string;
}

/** 右侧滑出抽屉：Esc 关闭、背景遮罩点击关闭、打开期间锁定页面滚动。 */
export function Drawer({
  open,
  onClose,
  title,
  subtitle,
  children,
  footer,
  widthClassName = "max-w-xl",
}: DrawerProps) {
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
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="animate-fade-in absolute inset-0 bg-ink/35 backdrop-blur-sm" onClick={onClose} />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={clsx(
          "animate-slide-in-right relative flex h-full w-full flex-col border-l border-line bg-paper shadow-[-30px_0_70px_-40px_rgba(32,29,24,0.7)]",
          widthClassName,
        )}
      >
        <header className="flex shrink-0 items-start justify-between gap-4 border-b border-line px-5 py-4">
          <div className="min-w-0">
            <h2 className="font-display text-xl tracking-wide text-ink">{title}</h2>
            {subtitle ? <p className="mt-1 text-xs text-ink-ghost">{subtitle}</p> : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="关闭"
            className="flex size-8 shrink-0 items-center justify-center rounded-lg text-ink-ghost transition-colors hover:bg-paper-sunk/70 hover:text-ink"
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
