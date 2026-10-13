import { useEffect, useRef, useState } from "react";

import type { DocumentItem } from "@/api/types";
import { useAuth } from "@/auth/AuthContext";
import { canWrite } from "@/auth/roles";
import { Drawer } from "@/components/ui/Drawer";
import { SelectField } from "@/components/ui/SelectField";
import type { SelectOption } from "@/components/ui/SelectField";
import { DocumentListPanel } from "@/document/DocumentListPanel";
import { useKnowledgeBases } from "@/document/KnowledgeBaseProvider";
import { QaListPanel } from "@/document/QaListPanel";

interface DocumentDrawerProps {
  open: boolean;
  onClose: () => void;
  /** 打开时优先选中的知识库（通常为对话页当前所选）。 */
  initialKb?: string | null;
}

/** 文档管理抽屉：知识库 -> 文档 -> 问答 -> 佐证材料 的四层维护。 */
export function DocumentDrawer({ open, onClose, initialKb }: DocumentDrawerProps) {
  const { kbs, reload } = useKnowledgeBases();
  const { user } = useAuth();
  const writable = canWrite(user?.role);

  const [kbName, setKbName] = useState<string | null>(null);
  const [activeDoc, setActiveDoc] = useState<DocumentItem | null>(null);
  // 仅在「抽屉由关到开」时定位知识库：避免数据刷新（kbs 变化）把用户当前选择重置
  const wasOpenRef = useRef(false);

  useEffect(() => {
    if (open && !wasOpenRef.current) {
      setActiveDoc(null);
      if (initialKb && kbs.some((kb) => kb.name === initialKb)) {
        setKbName(initialKb);
      }
    }
    wasOpenRef.current = open;
  }, [open, initialKb, kbs]);

  // 知识库列表变化时纠正选择（被删除或改名时回落）
  useEffect(() => {
    if (kbs.length === 0) {
      setKbName(null);
      setActiveDoc(null);
      return;
    }
    if (!kbName || !kbs.some((kb) => kb.name === kbName)) {
      setKbName(kbs[0].name);
      setActiveDoc(null);
    }
  }, [kbs, kbName]);

  const kbOptions: SelectOption[] =
    kbs.length === 0
      ? [{ value: "", label: "暂无知识库" }]
      : kbs.map((kb) => ({ value: kb.name, label: `${kb.name}（${kb.qa_count} 条问答）` }));

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title="文档管理"
      subtitle="按知识库维护文档、问答与佐证材料"
      widthClassName="max-w-2xl"
    >
      <div className="space-y-4">
        <SelectField
          label="知识库"
          value={kbName ?? ""}
          disabled={kbs.length === 0}
          options={kbOptions}
          onChange={(e) => {
            setKbName(e.target.value);
            setActiveDoc(null);
          }}
        />

        {!kbName ? (
          <p className="py-10 text-center text-xs text-ink-ghost">
            暂无知识库，请先在「知识库管理」中创建
          </p>
        ) : activeDoc ? (
          <QaListPanel
            kbName={kbName}
            document={activeDoc}
            writable={writable}
            onBack={() => setActiveDoc(null)}
            onChanged={reload}
          />
        ) : (
          <DocumentListPanel
            kbName={kbName}
            writable={writable}
            onOpen={setActiveDoc}
            onChanged={reload}
          />
        )}
      </div>
    </Drawer>
  );
}
