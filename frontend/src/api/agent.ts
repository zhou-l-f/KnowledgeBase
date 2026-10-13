import { http } from "@/api/client";
import type { InvokeRequest, InvokeResponse } from "@/api/types";

/** RAG 问答：在指定知识库中检索并生成回答；带 conversation_id 时续聊并注入历史记忆。 */
export function invoke(payload: InvokeRequest): Promise<InvokeResponse> {
  return http.post<InvokeResponse>("/agent/invoke", payload);
}
