import { clsx } from "clsx";
import { Check, ChevronDown, Database, Lock } from "lucide-react";
import { useRef, useState } from "react";

import type { KnowledgeBase } from "@/api/types";
import { useClickOutside } from "@/hooks/useClickOutside";

interface KnowledgeBasePickerProps {
  kbs: KnowledgeBase[];
  value: string | null;
  onChange: (name: string) => void;
  disabled?: boolean;
  /** 会话已绑定知识库：锁定选择并以锁形图标 + 悬停提示说明原因（窄屏下提示文字会隐藏）。 */
  locked?: boolean;
}

/** 知识库选择器：问答时用于指定检索目标（新会话的 invoke 必填 kb_name，续聊以会话绑定为准）。 */
export function KnowledgeBasePicker({
  kbs,
  value,
  onChange,
  disabled,
  locked,
}: KnowledgeBasePickerProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  useClickOutside(containerRef, () => setOpen(false), open);

  const selected = kbs.find((kb) => kb.name === value) ?? null;
  const label = selected?.name ?? (kbs.length > 0 ? "选择知识库" : "暂无知识库");

  return (
    <div
      ref={containerRef}
      className="relative"
      title={locked ? "当前会话已绑定知识库，续聊沿用该知识库" : undefined}
    >
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((prev) => !prev)}
        className={clsx(
          "flex h-9 max-w-[15rem] items-center gap-2 rounded-lg border border-line bg-paper-raised/75 px-3",
          "text-sm text-ink-soft transition-colors hover:border-ink-ghost hover:bg-paper-raised",
          "disabled:cursor-not-allowed disabled:opacity-50",
        )}
      >
        <Database className="size-4 shrink-0 text-jade" strokeWidth={1.8} />
        <span className={clsx("truncate", !selected && "text-ink-ghost")}>{label}</span>
        {locked ? (
          <Lock className="size-4 shrink-0 text-ink-ghost" strokeWidth={1.8} />
        ) : (
          <ChevronDown
            className={clsx(
              "size-4 shrink-0 text-ink-ghost transition-transform",
              open && "rotate-180",
            )}
            strokeWidth={1.8}
          />
        )}
      </button>

      {open ? (
        <div className="animate-rise-in absolute left-0 top-full z-30 mt-2 w-72 rounded-xl border border-line bg-paper-raised p-1.5 shadow-[0_28px_60px_-30px_rgba(32,29,24,0.65)]">
          {kbs.length === 0 ? (
            <p className="px-3 py-4 text-center text-xs text-ink-ghost">
              暂无知识库，请在「知识库管理」中创建并上传文档
            </p>
          ) : (
            <ul className="max-h-72 space-y-0.5 overflow-y-auto">
              {kbs.map((kb) => {
                const isActive = kb.name === value;
                return (
                  <li key={kb.id}>
                    <button
                      type="button"
                      onClick={() => {
                        onChange(kb.name);
                        setOpen(false);
                      }}
                      className={clsx(
                        "flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left transition-colors",
                        isActive ? "bg-cinnabar/10" : "hover:bg-paper-sunk/60",
                      )}
                    >
                      <div className="min-w-0 flex-1">
                        <div
                          className={clsx(
                            "truncate text-sm",
                            isActive ? "text-cinnabar" : "text-ink",
                          )}
                        >
                          {kb.name}
                        </div>
                        <div className="truncate text-[11px] text-ink-ghost">
                          {kb.description || "无描述"} · {kb.qa_count} 条问答
                        </div>
                      </div>
                      {isActive ? <Check className="size-4 shrink-0 text-cinnabar" strokeWidth={2} /> : null}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}
