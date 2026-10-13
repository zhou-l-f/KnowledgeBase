import type { MediaItem } from "@/api/types";

/** 对话消息状态：pending 表示模型正在检索/生成，error 表示本轮失败。 */
export type MessageStatus = "done" | "pending" | "error";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources: string[];
  media: MediaItem[];
  status: MessageStatus;
}

/** 会话摘要：由后端 /conversation 提供，侧边栏展示用（不含消息）。 */
export interface Conversation {
  id: string;
  title: string;
  kbName: string;
  createdAt: number;
  updatedAt: number;
}