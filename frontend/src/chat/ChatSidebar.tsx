import { clsx } from "clsx";
import {
  Database,
  Feather,
  FolderOpen,
  LogOut,
  MessageSquarePlus,
  Trash2,
  Users,
  X,
} from "lucide-react";

import { useAuth } from "@/auth/AuthContext";
import { isAdmin, roleLabel } from "@/auth/roles";
import type { Conversation } from "@/chat/types";
import { Spinner } from "@/components/ui/Spinner";

interface ChatSidebarProps {
  conversations: Conversation[];
  activeId: string | null;
  listLoading: boolean;
  listError: string | null;
  onNew: () => void;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onClose: () => void;
  onOpenKnowledgeBases: () => void;
  onOpenDocuments: () => void;
  onOpenUsers: () => void;
}

/** 左侧边栏：品牌、新建对话、历史会话列表（后端拉取）与用户信息。 */
export function ChatSidebar({
  conversations,
  activeId,
  listLoading,
  listError,
  onNew,
  onSelect,
  onDelete,
  onClose,
  onOpenKnowledgeBases,
  onOpenDocuments,
  onOpenUsers,
}: ChatSidebarProps) {
  const { user, logout } = useAuth();

  return (
    <div className="flex h-full flex-col bg-paper-raised/70">
      <div className="flex h-14 shrink-0 items-center gap-2.5 border-b border-line px-4">
        <Feather className="size-5 text-cinnabar" strokeWidth={1.7} />
        <span className="font-display text-lg tracking-wide text-ink">知识库智能问答</span>
        <button
          type="button"
          onClick={onClose}
          aria-label="收起侧边栏"
          className="ml-auto flex size-8 items-center justify-center rounded-lg text-ink-ghost transition-colors hover:bg-paper-sunk/60 hover:text-ink md:hidden"
        >
          <X className="size-4" />
        </button>
      </div>

      <div className="shrink-0 px-3 pt-3">
        <button
          type="button"
          onClick={onNew}
          className="flex w-full items-center justify-center gap-2 rounded-lg border border-cinnabar/30 bg-cinnabar/8 py-2.5 text-sm font-medium text-cinnabar transition-colors hover:bg-cinnabar/15"
        >
          <MessageSquarePlus className="size-4" strokeWidth={1.9} />
          新建对话
        </button>
      </div>

      <nav className="mt-3 flex-1 overflow-y-auto px-3 pb-3">
        <div className="mb-1.5 px-1 text-[11px] tracking-[0.18em] text-ink-ghost">历史会话</div>
        {listLoading ? (
          <div className="flex items-center justify-center gap-2 px-1 py-6 text-xs text-ink-ghost">
            <Spinner className="size-3.5" />
            载入中…
          </div>
        ) : listError ? (
          <p className="px-1 py-6 text-center text-xs text-cinnabar">{listError}</p>
        ) : conversations.length === 0 ? (
          <p className="px-1 py-6 text-center text-xs text-ink-ghost">暂无历史会话</p>
        ) : (
          <ul className="space-y-0.5">
            {conversations.map((conversation) => {
              const isActive = conversation.id === activeId;
              return (
                <li key={conversation.id} className="group relative">
                  <button
                    type="button"
                    onClick={() => onSelect(conversation.id)}
                    className={clsx(
                      "w-full rounded-lg px-3 py-2 pr-8 text-left transition-colors",
                      isActive ? "bg-cinnabar/10" : "hover:bg-paper-sunk/60",
                    )}
                  >
                    <span
                      className={clsx(
                        "block truncate text-sm",
                        isActive ? "text-cinnabar" : "text-ink-soft",
                      )}
                    >
                      {conversation.title}
                    </span>
                    {conversation.kbName ? (
                      <span className="mt-0.5 block truncate text-[11px] text-ink-ghost">
                        {conversation.kbName}
                      </span>
                    ) : null}
                  </button>
                  <button
                    type="button"
                    onClick={() => onDelete(conversation.id)}
                    aria-label="删除会话"
                    className="absolute right-1.5 top-1/2 flex size-6 -translate-y-1/2 items-center justify-center rounded-md text-ink-ghost opacity-60 transition-all hover:bg-cinnabar/12 hover:text-cinnabar focus-visible:opacity-100 md:opacity-0 md:group-hover:opacity-100 md:focus-visible:opacity-100"
                  >
                    <Trash2 className="size-3.5" />
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </nav>

      <div className="shrink-0 space-y-0.5 border-t border-line px-3 py-2">
        <button
          type="button"
          onClick={onOpenKnowledgeBases}
          className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-ink-faint transition-colors hover:bg-paper-sunk/60 hover:text-ink"
        >
          <Database className="size-4 shrink-0 text-jade" strokeWidth={1.9} />
          知识库管理
        </button>
        <button
          type="button"
          onClick={onOpenDocuments}
          className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-ink-faint transition-colors hover:bg-paper-sunk/60 hover:text-ink"
        >
          <FolderOpen className="size-4 shrink-0 text-jade" strokeWidth={1.9} />
          文档管理
        </button>
        {isAdmin(user?.role) ? (
          <button
            type="button"
            onClick={onOpenUsers}
            className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-ink-faint transition-colors hover:bg-paper-sunk/60 hover:text-ink"
          >
            <Users className="size-4 shrink-0 text-jade" strokeWidth={1.9} />
            用户管理
          </button>
        ) : null}
      </div>

      <div className="flex shrink-0 items-center gap-3 border-t border-line px-4 py-3">
        <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-ink font-display text-sm text-paper">
          {user?.user_id?.slice(0, 1).toUpperCase() ?? "?"}
        </div>
        <div className="min-w-0 flex-1 leading-tight">
          <div className="truncate text-sm text-ink">{user?.user_id}</div>
          <div className="text-[11px] text-ink-ghost">{roleLabel(user?.role)}</div>
        </div>
        <button
          type="button"
          onClick={logout}
          aria-label="退出登录"
          title="退出登录"
          className="flex size-8 items-center justify-center rounded-lg text-ink-ghost transition-colors hover:bg-paper-sunk/60 hover:text-cinnabar"
        >
          <LogOut className="size-4" />
        </button>
      </div>
    </div>
  );
}
