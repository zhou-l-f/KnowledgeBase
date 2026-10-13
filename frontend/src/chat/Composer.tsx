import { ArrowUp } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent } from "react";

import { clsx } from "clsx";

interface ComposerProps {
  disabled: boolean;
  sending: boolean;
  placeholder: string;
  onSend: (text: string) => void;
}

const MAX_HEIGHT = 200;

/** 底部输入区：Enter 发送、Shift+Enter 换行，输入框随内容自适应高度。 */
export function Composer({ disabled, sending, placeholder, onSend }: ComposerProps) {
  const [text, setText] = useState("");
  const [composing, setComposing] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // 内容变化时重算高度（先归零再取 scrollHeight，才能正确收缩）
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT)}px`;
  }, [text]);

  const canSend = !disabled && !sending && text.trim().length > 0;

  function submit() {
    const value = text.trim();
    if (!value || disabled || sending) return;
    onSend(value);
    setText("");
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // 中文输入法组词期间的回车不触发发送
    if (event.key === "Enter" && !event.shiftKey && !composing) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <div className="border-t border-line bg-paper-raised/60 px-4 py-3 backdrop-blur-sm">
      <div className="mx-auto flex max-w-3xl items-end gap-2">
        <div className="flex-1 rounded-xl border border-line bg-paper-raised transition-colors focus-within:border-cinnabar/55 focus-within:ring-2 focus-within:ring-cinnabar/12">
          <textarea
            ref={textareaRef}
            rows={1}
            value={text}
            disabled={disabled}
            placeholder={placeholder}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            onCompositionStart={() => setComposing(true)}
            onCompositionEnd={() => setComposing(false)}
            className={clsx(
              "block max-h-[200px] w-full resize-none bg-transparent px-3.5 py-2.5 text-sm leading-relaxed text-ink",
              "placeholder:text-ink-ghost/80 focus:outline-none disabled:cursor-not-allowed",
            )}
          />
        </div>
        <button
          type="button"
          disabled={!canSend}
          onClick={submit}
          aria-label="发送"
          className={clsx(
            "flex size-10 shrink-0 items-center justify-center rounded-xl transition-all",
            canSend
              ? "bg-cinnabar text-paper-raised shadow-[0_8px_20px_-10px_rgba(165,50,29,0.9)] hover:bg-cinnabar-soft active:translate-y-px"
              : "bg-paper-sunk text-ink-ghost",
          )}
        >
          <ArrowUp className="size-5" strokeWidth={2.2} />
        </button>
      </div>
      <p className="mx-auto mt-2 max-w-3xl text-center text-[11px] text-ink-ghost">
        Enter 发送 · Shift + Enter 换行 · 回答严格依据知识库资料生成
      </p>
    </div>
  );
}
