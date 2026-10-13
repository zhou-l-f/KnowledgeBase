import { FileText, TriangleAlert } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { MediaGallery } from "@/chat/MediaGallery";
import type { ChatMessage } from "@/chat/types";

/** 模型正在检索/生成时的等待指示：三点错峰脉冲。 */
function ThinkingIndicator() {
  return (
    <div className="flex items-center gap-2.5 text-sm text-ink-faint">
      <span className="flex gap-1">
        {[0, 1, 2].map((index) => (
          <span
            key={index}
            className="animate-ink-pulse size-1.5 rounded-full bg-cinnabar"
            style={{ animationDelay: `${index * 0.2}s` }}
          />
        ))}
      </span>
      <span>正在检索知识库并生成回答…</span>
    </div>
  );
}

function Sources({ sources }: { sources: string[] }) {
  return (
    <div>
      <div className="mb-1.5 text-[11px] tracking-wide text-ink-ghost">参考来源</div>
      <div className="flex flex-wrap gap-1.5">
        {sources.map((source) => (
          <span
            key={source}
            className="inline-flex items-center gap-1.5 rounded-md border border-line bg-paper-sunk/50 px-2 py-1 text-[11px] text-ink-faint"
          >
            <FileText className="size-3 text-jade" strokeWidth={1.9} />
            {source || "未知来源"}
          </span>
        ))}
      </div>
    </div>
  );
}

/** 单条对话消息：用户靠右墨色气泡，助手靠左纸色气泡并附来源与佐证材料。 */
export function MessageBubble({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div className="animate-rise-in flex justify-end">
        <div className="max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-ink px-4 py-2.5 text-sm leading-relaxed text-paper shadow-[0_12px_28px_-18px_rgba(32,29,24,0.9)]">
          {message.content}
        </div>
      </div>
    );
  }

  const isError = message.status === "error";

  return (
    <div className="animate-rise-in flex gap-3">
      <div className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-md bg-cinnabar font-display text-base leading-none text-paper-raised shadow-[0_8px_18px_-10px_rgba(165,50,29,0.9)]">
        知
      </div>

      <div className="min-w-0 max-w-[80%] space-y-3">
        <div
          className={
            isError
              ? "rounded-2xl rounded-tl-md border border-cinnabar/25 bg-cinnabar/8 px-4 py-3"
              : "rounded-2xl rounded-tl-md border border-line bg-paper-raised/85 px-4 py-3 shadow-[0_12px_30px_-24px_rgba(32,29,24,0.7)]"
          }
        >
          {message.status === "pending" ? (
            <ThinkingIndicator />
          ) : isError ? (
            <div className="flex items-start gap-2 text-sm text-cinnabar">
              <TriangleAlert className="mt-0.5 size-4 shrink-0" strokeWidth={1.9} />
              <span>{message.content}</span>
            </div>
          ) : (
            <div className="md-body text-ink-soft">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
            </div>
          )}
        </div>

        {message.status === "done" && message.sources.length > 0 ? (
          <Sources sources={message.sources} />
        ) : null}
        {message.status === "done" ? <MediaGallery items={message.media} /> : null}
      </div>
    </div>
  );
}
