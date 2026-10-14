import { LockKeyhole, UserRound } from "lucide-react";
import { useState } from "react";
import type { FormEvent } from "react";

import { ApiError } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";

/** 登录页：未登录时全屏展示（非独立路由）。 */
export function LoginPage() {
  const { login } = useAuth();
  const [userId, setUserId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = userId.trim();
    if (!trimmed || !password) {
      setError("请输入用户ID与密码");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await login(trimmed, password);
      // 登录成功后本组件随状态切换卸载，无需重置 submitting
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "登录失败，请稍后重试");
      setSubmitting(false);
    }
  }

  return (
    <main className="relative flex min-h-full items-center justify-center px-6 py-12">
      {/* 角落墨晕装饰，避免大面积纯色留白 */}
      <div
        aria-hidden
        className="pointer-events-none absolute -left-32 -top-32 size-96 rounded-full bg-jade/10 blur-3xl"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute -bottom-40 -right-24 size-[28rem] rounded-full bg-cinnabar/10 blur-3xl"
      />

      <div className="animate-rise-in relative w-full max-w-sm rounded-2xl border border-line bg-paper-raised/85 p-8 shadow-[0_36px_80px_-48px_rgba(32,29,24,0.75)] backdrop-blur-sm">
        <div className="mb-7 flex flex-col items-center text-center">
          <div className="mb-5 flex size-14 -rotate-3 items-center justify-center rounded-lg bg-cinnabar text-paper-raised shadow-[0_12px_26px_-14px_rgba(165,50,29,0.95)]">
            <span className="font-display text-2xl leading-none">知</span>
          </div>
          <h1 className="font-display text-3xl tracking-wide text-ink">知库</h1>
          <p className="mt-2 text-xs tracking-[0.2em] text-ink-ghost">企业内部知识检索 · 问答助手</p>
        </div>

        <form className="space-y-4" onSubmit={handleSubmit}>
          <TextField
            label="用户ID"
            icon={<UserRound className="size-4" strokeWidth={1.8} />}
            placeholder="请输入用户ID"
            autoComplete="username"
            autoFocus
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
          />
          <TextField
            label="密码"
            type="password"
            icon={<LockKeyhole className="size-4" strokeWidth={1.8} />}
            placeholder="请输入密码"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          {error ? (
            <p className="rounded-lg border border-cinnabar/25 bg-cinnabar/8 px-3 py-2 text-xs text-cinnabar">
              {error}
            </p>
          ) : null}

          <Button type="submit" loading={submitting} className="w-full">
            {submitting ? "登录中…" : "登 录"}
          </Button>
        </form>

        <div className="mt-6 flex items-center gap-3 text-[11px] text-ink-ghost">
          <span className="h-px flex-1 bg-line-soft" />
          <span>请使用管理员分配的账号登录</span>
          <span className="h-px flex-1 bg-line-soft" />
        </div>
      </div>
    </main>
  );
}
