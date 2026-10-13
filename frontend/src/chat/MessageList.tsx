import { MessageSquareText } from "lucide-react";
import { useEffect, useRef } from "react";

import { MessageBubble } from "@/chat/MessageBubble";
import type { ChatMessage } from "@/chat/types";
import { Spinner } from "@/components/ui/Spinner";

interface MessageListProps {
  messages: ChatMessage[];
  kbName: string | null;
  hasKb: boolean;
  /** 历史会话详情加载中：隐藏消息区，避免闪现空态。 */
  loading?: boolean;
}

/** 无消息时的引导页：说明当前知识库与提问方式。 */
function EmptyState({ kbName, hasKb }: { kbName: string | null; hasKb: boolean }) {
  return (
    <div className="animate-rise-in flex h-full flex-col items-center justify-center px-6 text-center">
      <div className="mb-6 flex size-16 items-center justify-center rounded-2xl border border-line bg-paper-raised shadow-[0_18px_40px_-28px_rgba(32,29,24,0.8)]">
        <span className="font-display text-3xl leading-none text-cinnabar">知</span>
      </div>
      <h2 className="font-display text-2xl tracking-wide text-ink">有问必答</h2>
      <p className="mt-2 max-w-md text-sm leading-relaxed text-ink-faint">
        {hasKb && kbName ? (
          <>
            当前知识库为「<span className="text-cinnabar">{kbName}</span>
            」，回答将严格依据其中的资料生成。
          </>
        ) : (
          "尚未选择知识库，请先在顶部选择或前往「知识库管理」创建知识库并上传文档。"
        )}
      </p>
      {hasKb ? (
        <div className="mt-6 flex items-center gap-2 text-[11px] text-ink-ghost">
          <MessageSquareText className="size-3.5" />
          <span>在下方输入问题开始对话</span>
        </div>
      ) : null}
    </div>
  );
}

/** 消息流：自动滚动到底部（用户上滑查看历史时不打断）。 */
export function MessageList({ messages, kbName, hasKb, loading }: MessageListProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const nearBottomRef = useRef(true);

  function handleScroll() {
    const el = scrollRef.current;
    if (!el) return;
    nearBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  }

  useEffect(() => {
    if (!nearBottomRef.current) return;
    const el = scrollRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages, loading]);

  return (
    <div
      ref={scrollRef}
      onScroll={handleScroll}
      role="log"
      aria-live="polite"
      aria-relevant="additions"
      className="flex-1 overflow-y-auto px-4 py-6"
    >
      <div className="mx-auto flex h-full max-w-3xl flex-col gap-5">
        {loading ? (
          <div className="flex h-full items-center justify-center gap-2 text-sm text-ink-faint">
            <Spinner className="text-cinnabar" />
            <span>正在加载会话记录…</span>
          </div>
        ) : messages.length === 0 ? (
          <EmptyState kbName={kbName} hasKb={hasKb} />
        ) : (
          messages.map((message) => <MessageBubble key={message.id} message={message} />)
        )}
      </div>
    </div>
  );
}
