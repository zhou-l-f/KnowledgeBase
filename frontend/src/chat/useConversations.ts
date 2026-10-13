import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "@/api/client";
import { deleteConversation, getConversation, listConversations } from "@/api/conversation";
import type { ConversationDetail, ConversationMessage, ConversationSummary } from "@/api/types";
import type { ChatMessage, Conversation } from "@/chat/types";

/** 生成消息的本地临时 id（仅用于乐观渲染，落库 id 由后端返回）。 */
export function createId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

/** 后端会话摘要 → 前端侧边栏模型（snake_case 转 camelCase）。 */
export function toConversation(summary: ConversationSummary): Conversation {
  return {
    id: summary.id,
    title: summary.title,
    kbName: summary.kb_name,
    createdAt: summary.created_at,
    updatedAt: summary.updated_at,
  };
}

/** 后端消息 → 前端消息模型；后端只落库成功轮次，故历史消息一律为完成态。 */
export function toChatMessage(message: ConversationMessage): ChatMessage {
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    sources: message.sources,
    media: message.media,
    status: "done",
  };
}

/**
 * 会话管理：历史对话的唯一真源在后端（/conversation），本 Hook 只负责拉取与同步。
 * 新建会话由后端在首轮问答成功后创建，前端不再本地生成空会话。
 */
export function useConversations() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  /** 重新拉取会话列表（发送成功、删除后调用，用于刷新顺序与标题）。 */
  const reload = useCallback(async () => {
    try {
      const items = await listConversations();
      if (!mountedRef.current) return;
      setConversations(items.map(toConversation));
      setListError(null);
    } catch (err) {
      if (!mountedRef.current) return;
      setListError(err instanceof ApiError ? err.message : "会话列表加载失败");
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void (async () => {
      setListLoading(true);
      await reload();
      if (mountedRef.current) setListLoading(false);
    })();
    return () => {
      mountedRef.current = false;
    };
  }, [reload]);

  /** 加载指定会话详情（含全部消息），供切换历史会话时使用。 */
  const loadDetail = useCallback(
    (id: string): Promise<ConversationDetail> => getConversation(id),
    [],
  );

  /** 删除会话：后端删除成功后同步移除本地列表项。 */
  const remove = useCallback(async (id: string) => {
    await deleteConversation(id);
    setConversations((prev) => prev.filter((item) => item.id !== id));
  }, []);

  return { conversations, listLoading, listError, reload, loadDetail, remove };
}