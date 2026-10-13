import { clsx } from "clsx";
import { Menu, TriangleAlert } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { invoke } from "@/api/agent";
import { ApiError } from "@/api/client";
import { UserManagementModal } from "@/auth/UserManagementModal";
import { ChatSidebar } from "@/chat/ChatSidebar";
import { Composer } from "@/chat/Composer";
import { KnowledgeBasePicker } from "@/chat/KnowledgeBasePicker";
import { MessageList } from "@/chat/MessageList";
import type { ChatMessage } from "@/chat/types";
import { createId, toChatMessage, useConversations } from "@/chat/useConversations";
import { DocumentDrawer } from "@/document/DocumentDrawer";
import { KnowledgeBaseDrawer } from "@/document/KnowledgeBaseDrawer";
import { useKnowledgeBases } from "@/document/KnowledgeBaseProvider";

const SELECTED_KB_KEY = "kb.selected_kb.v1";

/** 对话主页：会话记忆由后端托管（/conversation），本页负责编排历史加载与 RAG 问答。 */
export function ChatPage() {
  const { kbs, loading: kbLoading, error: kbError } = useKnowledgeBases();
  const { conversations, listLoading, listError, reload, loadDetail, remove } = useConversations();

  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [selectedKb, setSelectedKb] = useState<string | null>(() =>
    localStorage.getItem(SELECTED_KB_KEY),
  );
  const [sending, setSending] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [kbDrawerOpen, setKbDrawerOpen] = useState(false);
  const [docDrawerOpen, setDocDrawerOpen] = useState(false);
  const [usersModalOpen, setUsersModalOpen] = useState(false);

  // 快速连续切换会话时，用序号丢弃过期详情响应
  const selectSeqRef = useRef(0);

  // 方案 A：历史会话已绑定知识库，续聊时以会话绑定为准，故锁定选择器
  const kbLocked = activeId !== null;

  // 记住最近使用的知识库（仅影响新会话的默认选项）
  useEffect(() => {
    if (selectedKb) {
      localStorage.setItem(SELECTED_KB_KEY, selectedKb);
    } else {
      localStorage.removeItem(SELECTED_KB_KEY);
    }
  }, [selectedKb]);

  // 知识库列表变化时纠正选择：不存在则回落到第一个（锁定期间不干预，以会话绑定为准）
  useEffect(() => {
    if (kbLocked) return;
    if (kbs.length === 0) {
      if (selectedKb !== null) setSelectedKb(null);
      return;
    }
    if (!selectedKb || !kbs.some((kb) => kb.name === selectedKb)) {
      setSelectedKb(kbs[0].name);
    }
  }, [kbs, selectedKb, kbLocked]);

  /** 新建对话：清空当前视图（会话由后端在首轮问答成功后创建）。 */
  const handleNew = useCallback(() => {
    selectSeqRef.current += 1; // 使在途的详情加载失效
    setActiveId(null);
    setMessages([]);
    setDetailLoading(false);
    setActionError(null);
    setSidebarOpen(false);
  }, []);

  /** 切换历史会话：拉取详情并回填消息与绑定知识库。 */
  const handleSelect = useCallback(
    async (id: string) => {
      setSidebarOpen(false);
      setActiveId(id);
      setMessages([]);
      setDetailLoading(true);
      setActionError(null);
      const seq = ++selectSeqRef.current;
      try {
        const detail = await loadDetail(id);
        if (selectSeqRef.current !== seq) return;
        setMessages(detail.messages.map(toChatMessage));
        setSelectedKb(detail.kb_name);
      } catch (err) {
        if (selectSeqRef.current !== seq) return;
        setActionError(err instanceof ApiError ? err.message : "会话记录加载失败");
      } finally {
        if (selectSeqRef.current === seq) setDetailLoading(false);
      }
    },
    [loadDetail],
  );

  /** 删除历史会话：后端删除成功后同步列表；删除的是当前会话则回到新对话。 */
  const handleDelete = useCallback(
    async (id: string) => {
      setActionError(null);
      try {
        await remove(id);
        if (activeId === id) {
          selectSeqRef.current += 1;
          setActiveId(null);
          setMessages([]);
          setDetailLoading(false);
        }
      } catch (err) {
        setActionError(err instanceof ApiError ? err.message : "删除会话失败");
        void reload();
      }
    },
    [activeId, reload, remove],
  );

  /** 发送提问：无 activeId 时由后端开启新会话，有则续聊（后端注入历史记忆）。 */
  const handleSend = useCallback(
    async (text: string) => {
      if (sending) return;
      if (!activeId && !selectedKb) return;

      const userMessage: ChatMessage = {
        id: createId(),
        role: "user",
        content: text,
        sources: [],
        media: [],
        status: "done",
      };
      const assistantId = createId();
      const assistantMessage: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        sources: [],
        media: [],
        status: "pending",
      };
      setMessages((prev) => [...prev, userMessage, assistantMessage]);
      setActionError(null);
      setSending(true);

      try {
        const result = await invoke({
          question: text,
          kb_name: selectedKb,
          conversation_id: activeId,
        });
        if (!activeId) {
          setActiveId(result.conversation_id);
        }
        setMessages((prev) =>
          prev.map((item) =>
            item.id === assistantId
              ? {
                  ...item,
                  content: result.answer,
                  sources: result.sources,
                  media: result.media,
                  status: "done" as const,
                }
              : item,
          ),
        );
        void reload(); // 刷新标题与最近更新排序
      } catch (err) {
        const message = err instanceof ApiError ? err.message : "回答生成失败，请稍后重试";
        setMessages((prev) =>
          prev.map((item) =>
            item.id === assistantId ? { ...item, content: message, status: "error" as const } : item,
          ),
        );
      } finally {
        setSending(false);
      }
    },
    [activeId, reload, selectedKb, sending],
  );

  const banner = actionError ?? kbError;
  const placeholder = !selectedKb ? "请先选择知识库后再提问" : "输入问题，向知识库提问…";
  const hint = sending
    ? "正在生成回答…"
    : kbLocked
      ? "当前会话已绑定知识库，续聊沿用该知识库"
      : "回答仅依据所选知识库资料生成";

  return (
    <div className="flex h-full overflow-hidden">
      {/* 移动端遮罩 */}
      {sidebarOpen ? (
        <div
          className="fixed inset-0 z-30 bg-ink/30 backdrop-blur-sm md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      ) : null}

      <aside
        className={clsx(
          "fixed inset-y-0 left-0 z-40 w-72 shrink-0 border-r border-line transition-transform duration-300 md:static md:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <ChatSidebar
          conversations={conversations}
          activeId={activeId}
          listLoading={listLoading}
          listError={listError}
          onNew={handleNew}
          onSelect={handleSelect}
          onDelete={handleDelete}
          onClose={() => setSidebarOpen(false)}
          onOpenKnowledgeBases={() => setKbDrawerOpen(true)}
          onOpenDocuments={() => setDocDrawerOpen(true)}
          onOpenUsers={() => setUsersModalOpen(true)}
        />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-3 border-b border-line bg-paper-raised/60 px-4 backdrop-blur-sm">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            aria-label="展开侧边栏"
            className="flex size-9 items-center justify-center rounded-lg text-ink-faint transition-colors hover:bg-paper-sunk/60 hover:text-ink md:hidden"
          >
            <Menu className="size-5" />
          </button>
          <KnowledgeBasePicker
            kbs={kbs}
            value={selectedKb}
            onChange={setSelectedKb}
            disabled={kbLoading || kbs.length === 0 || kbLocked}
            locked={kbLocked}
          />
          <span className="hidden truncate text-xs text-ink-ghost sm:block">{hint}</span>
        </header>

        {banner ? (
          <div className="flex items-center gap-2 border-b border-cinnabar/20 bg-cinnabar/8 px-4 py-2 text-xs text-cinnabar">
            <TriangleAlert className="size-3.5 shrink-0" />
            {banner}
          </div>
        ) : null}

        <MessageList
          messages={messages}
          kbName={selectedKb}
          hasKb={selectedKb !== null}
          loading={detailLoading}
        />
        <Composer
          disabled={!selectedKb}
          sending={sending}
          placeholder={placeholder}
          onSend={handleSend}
        />
      </div>

      <KnowledgeBaseDrawer open={kbDrawerOpen} onClose={() => setKbDrawerOpen(false)} />
      <DocumentDrawer
        open={docDrawerOpen}
        onClose={() => setDocDrawerOpen(false)}
        initialKb={selectedKb}
      />
      <UserManagementModal open={usersModalOpen} onClose={() => setUsersModalOpen(false)} />
    </div>
  );
}