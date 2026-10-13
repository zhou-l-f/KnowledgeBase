import { AuthProvider, useAuth } from "@/auth/AuthContext";
import { LoginPage } from "@/auth/LoginPage";
import { ChatPage } from "@/chat/ChatPage";
import { KnowledgeBaseProvider } from "@/document/KnowledgeBaseProvider";

/** 启动自检时的过渡页：避免令牌校验期间闪现登录页。 */
function BootSplash() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4">
      <div className="animate-ink-pulse flex size-12 items-center justify-center rounded-lg bg-cinnabar text-paper-raised">
        <span className="font-display text-xl leading-none">知</span>
      </div>
      <p className="text-xs tracking-[0.3em] text-ink-ghost">正在校验登录状态…</p>
    </div>
  );
}

function AuthenticatedApp() {
  return (
    <KnowledgeBaseProvider>
      <ChatPage />
    </KnowledgeBaseProvider>
  );
}

function RootView() {
  const { status } = useAuth();
  if (status === "checking") return <BootSplash />;
  if (status === "anonymous") return <LoginPage />;
  return <AuthenticatedApp />;
}

export default function App() {
  return (
    <AuthProvider>
      <RootView />
    </AuthProvider>
  );
}
