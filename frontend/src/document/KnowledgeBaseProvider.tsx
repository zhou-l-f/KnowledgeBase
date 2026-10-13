import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { ApiError } from "@/api/client";
import { listKnowledgeBases } from "@/api/document";
import type { KnowledgeBase } from "@/api/types";

interface KnowledgeBaseContextValue {
  kbs: KnowledgeBase[];
  loading: boolean;
  error: string | null;
  /** 重新拉取知识库列表（知识库增删改后调用，保持各视图同步）。 */
  reload: () => Promise<void>;
}

const KnowledgeBaseContext = createContext<KnowledgeBaseContextValue | null>(null);

/** 全局知识库列表：对话页与知识库/文档管理共用同一份数据并保持同步。 */
export function KnowledgeBaseProvider({ children }: { children: ReactNode }) {
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setError(null);
    try {
      setKbs(await listKnowledgeBases());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "知识库列表加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const value = useMemo<KnowledgeBaseContextValue>(
    () => ({ kbs, loading, error, reload }),
    [kbs, loading, error, reload],
  );

  return <KnowledgeBaseContext.Provider value={value}>{children}</KnowledgeBaseContext.Provider>;
}

export function useKnowledgeBases(): KnowledgeBaseContextValue {
  const ctx = useContext(KnowledgeBaseContext);
  if (!ctx) {
    throw new Error("useKnowledgeBases 必须在 KnowledgeBaseProvider 内部使用");
  }
  return ctx;
}
