import { http } from "@/api/client";
import type { ConversationDetail, ConversationSummary } from "@/api/types";

/** 列出当前登录用户的历史会话（按最近更新倒序）。 */
export function listConversations(): Promise<ConversationSummary[]> {
  return http.get<ConversationSummary[]>("/conversation/conversations");
}

/** 获取指定会话详情（含全部消息）。 */
export function getConversation(conversationId: string): Promise<ConversationDetail> {
  return http.get<ConversationDetail>(
    `/conversation/conversations/${encodeURIComponent(conversationId)}`,
  );
}

/** 删除指定会话及其全部消息。 */
export function deleteConversation(conversationId: string): Promise<void> {
  return http.del<void>(`/conversation/conversations/${encodeURIComponent(conversationId)}`);
}