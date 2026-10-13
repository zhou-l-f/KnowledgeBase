/** 与后端 Pydantic Schema 对应的接口类型定义（仅类型，无运行时代码）。 */

// ---------------------------------------------------------------------------
// 认证（/auth）
// ---------------------------------------------------------------------------

export type Role = "admin" | "editor" | "readonly";

export interface LoginRequest {
  user_id: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

/** GET /auth/me：当前登录用户，含角色供前端控制界面显隐。 */
export interface CurrentUser {
  user_id: string;
  role: Role;
}

export interface UserCreate {
  user_id: string;
  password: string;
  role: Role;
}

export interface UserUpdate {
  password?: string;
  role?: Role;
}

export interface UserOut {
  user_id: string;
  role: Role;
  created_at: string;
}

// ---------------------------------------------------------------------------
// 文档管理（/document）
// ---------------------------------------------------------------------------

export interface KnowledgeBase {
  id: number;
  name: string;
  description: string;
  qa_count: number;
}

export interface KnowledgeBaseCreate {
  name: string;
  description?: string;
}

export interface KnowledgeBaseUpdate {
  name?: string;
  description?: string;
}

export interface DocumentItem {
  id: number;
  name: string;
  qa_count: number;
}

export interface DocumentUploadResult {
  document_id: number;
  name: string;
  qa_count: number;
  replaced: boolean;
}

export interface QaItem {
  id: number;
  question: string;
  answer: string;
}

export interface QaWrite {
  question: string;
  answer: string;
}

export interface MediaItem {
  id: number;
  qa_id: number;
  filename: string;
  mime_type: string;
  size: number;
  url: string;
}

// ---------------------------------------------------------------------------
// 问答（/agent）
// ---------------------------------------------------------------------------

export interface InvokeRequest {
  question: string;
  /** 目标知识库；开启新会话时必填，续聊时后端以会话绑定的知识库为准 */
  kb_name?: string | null;
  /** 续聊的会话 id；不传则由后端开启新会话 */
  conversation_id?: string | null;
}

export interface InvokeResponse {
  answer: string;
  sources: string[];
  media: MediaItem[];
  /** 本轮问答所属会话 id（新建或续聊） */
  conversation_id: string;
}

// ---------------------------------------------------------------------------
// 会话历史（/conversation）
// ---------------------------------------------------------------------------

/** 会话摘要：列表展示用，不含消息；时间为毫秒时间戳。 */
export interface ConversationSummary {
  id: string;
  title: string;
  kb_name: string;
  created_at: number;
  updated_at: number;
}

/** 会话消息：sources 与 media 为该轮问答的引用来源与佐证材料快照。 */
export interface ConversationMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources: string[];
  media: MediaItem[];
  status: string;
  created_at: number;
}

/** 会话详情：含全部消息（按时间顺序）。 */
export interface ConversationDetail extends ConversationSummary {
  messages: ConversationMessage[];
}
