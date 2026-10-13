import { clsx } from "clsx";
import { Pencil, Trash2, UserPlus } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import * as authApi from "@/api/auth";
import { ApiError } from "@/api/client";
import type { Role, UserOut } from "@/api/types";
import { useAuth } from "@/auth/AuthContext";
import { ROLE_LABELS } from "@/auth/roles";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Modal } from "@/components/ui/Modal";
import { SelectField } from "@/components/ui/SelectField";
import type { SelectOption } from "@/components/ui/SelectField";
import { Spinner } from "@/components/ui/Spinner";
import { TextField } from "@/components/ui/TextField";

const ROLE_OPTIONS: SelectOption[] = [
  { value: "admin", label: "管理员（全部权限）" },
  { value: "editor", label: "编辑（可维护知识库与文档）" },
  { value: "readonly", label: "只读（仅问答与查看）" },
];

const ROLE_BADGE: Record<Role, string> = {
  admin: "bg-cinnabar/12 text-cinnabar",
  editor: "bg-jade/12 text-jade",
  readonly: "bg-paper-sunk text-ink-faint",
};

interface CreateUserFormProps {
  busy: boolean;
  error: string | null;
  onSubmit: (userId: string, password: string, role: Role) => void;
  onCancel: () => void;
}

function CreateUserForm({ busy, error, onSubmit, onCancel }: CreateUserFormProps) {
  const [userId, setUserId] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>("readonly");

  return (
    <div className="space-y-3 rounded-xl border border-cinnabar/25 bg-cinnabar/6 p-3.5">
      <TextField
        label="用户ID"
        autoFocus
        maxLength={64}
        placeholder="登录用的唯一 ID"
        value={userId}
        onChange={(e) => setUserId(e.target.value)}
      />
      <TextField
        label="初始密码"
        type="password"
        maxLength={128}
        autoComplete="new-password"
        placeholder="至少 6 位"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      <SelectField
        label="角色"
        value={role}
        options={ROLE_OPTIONS}
        onChange={(e) => setRole(e.target.value as Role)}
      />
      {error ? <p className="text-xs text-cinnabar">{error}</p> : null}
      <div className="flex justify-end gap-2">
        <Button variant="outline" size="sm" onClick={onCancel} disabled={busy}>
          取消
        </Button>
        <Button
          size="sm"
          loading={busy}
          onClick={() => onSubmit(userId.trim(), password, role)}
        >
          创建
        </Button>
      </div>
    </div>
  );
}

interface EditUserFormProps {
  target: UserOut;
  isSelf: boolean;
  busy: boolean;
  error: string | null;
  onSubmit: (password: string, role: Role) => void;
  onCancel: () => void;
}

function EditUserForm({ target, isSelf, busy, error, onSubmit, onCancel }: EditUserFormProps) {
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>(target.role);

  return (
    <div className="space-y-3 rounded-xl border border-cinnabar/25 bg-cinnabar/6 p-3.5">
      <TextField
        label="重置密码（留空则不修改）"
        type="password"
        autoFocus
        maxLength={128}
        autoComplete="new-password"
        placeholder="至少 6 位"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      <SelectField
        label="角色"
        value={role}
        options={ROLE_OPTIONS}
        disabled={isSelf}
        hint={isSelf ? "不能修改自己的角色，请让其他管理员操作" : undefined}
        onChange={(e) => setRole(e.target.value as Role)}
      />
      {error ? <p className="text-xs text-cinnabar">{error}</p> : null}
      <div className="flex justify-end gap-2">
        <Button variant="outline" size="sm" onClick={onCancel} disabled={busy}>
          取消
        </Button>
        <Button size="sm" loading={busy} onClick={() => onSubmit(password, role)}>
          保存
        </Button>
      </div>
    </div>
  );
}

/** 用户管理弹窗：仅管理员可见，支持新建 / 重置密码 / 改角色 / 删除。 */
export function UserManagementModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { user: current } = useAuth();
  const [users, setUsers] = useState<UserOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [mode, setMode] = useState<"idle" | "create" | "edit">("idle");
  const [editTarget, setEditTarget] = useState<UserOut | null>(null);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<UserOut | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setUsers(await authApi.listUsers());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "用户列表加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    setMode("idle");
    setEditTarget(null);
    setFormError(null);
    void load();
  }, [open, load]);

  function resetForm() {
    setMode("idle");
    setEditTarget(null);
    setFormError(null);
  }

  async function handleCreate(userId: string, password: string, role: Role) {
    if (!userId) {
      setFormError("用户ID不能为空");
      return;
    }
    if (password.length < 6) {
      setFormError("密码至少 6 位");
      return;
    }
    setBusy(true);
    setFormError(null);
    try {
      await authApi.createUser({ user_id: userId, password, role });
      await load();
      resetForm();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "创建失败，请稍后重试");
    } finally {
      setBusy(false);
    }
  }

  async function handleUpdate(password: string, role: Role) {
    if (!editTarget) return;
    const changingPassword = password.length > 0;
    const changingRole = role !== editTarget.role;
    if (changingPassword && password.length < 6) {
      setFormError("密码至少 6 位");
      return;
    }
    if (!changingPassword && !changingRole) {
      setFormError("未做任何修改");
      return;
    }
    setBusy(true);
    setFormError(null);
    try {
      await authApi.updateUser(editTarget.user_id, {
        password: changingPassword ? password : undefined,
        role: changingRole ? role : undefined,
      });
      await load();
      resetForm();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "保存失败，请稍后重试");
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    if (!pendingDelete) return;
    setDeleteBusy(true);
    setDeleteError(null);
    try {
      await authApi.deleteUser(pendingDelete.user_id);
      await load();
      setPendingDelete(null);
    } catch (err) {
      setDeleteError(err instanceof ApiError ? err.message : "删除失败，请稍后重试");
    } finally {
      setDeleteBusy(false);
    }
  }

  return (
    <>
      <Modal open={open} onClose={onClose} title="用户管理" widthClassName="max-w-2xl">
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-ink-ghost">共 {users.length} 个用户 · 角色决定可执行的操作</p>
            {mode !== "create" ? (
              <Button
                size="sm"
                icon={<UserPlus className="size-4" />}
                onClick={() => {
                  setMode("create");
                  setEditTarget(null);
                  setFormError(null);
                }}
              >
                新建用户
              </Button>
            ) : null}
          </div>

          {mode === "create" ? (
            <CreateUserForm
              busy={busy}
              error={formError}
              onSubmit={handleCreate}
              onCancel={resetForm}
            />
          ) : null}

          {loading ? (
            <div className="flex justify-center py-10">
              <Spinner className="size-5 text-ink-ghost" />
            </div>
          ) : error ? (
            <p className="rounded-lg border border-cinnabar/25 bg-cinnabar/8 px-3 py-2 text-xs text-cinnabar">
              {error}
            </p>
          ) : (
            <ul className="space-y-2.5">
              {users.map((item) => {
                const isSelf = item.user_id === current?.user_id;
                return (
                  <li
                    key={item.user_id}
                    className="rounded-xl border border-line bg-paper-raised p-3.5"
                  >
                    {mode === "edit" && editTarget?.user_id === item.user_id ? (
                      <EditUserForm
                        target={item}
                        isSelf={isSelf}
                        busy={busy}
                        error={formError}
                        onSubmit={handleUpdate}
                        onCancel={resetForm}
                      />
                    ) : (
                      <>
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex min-w-0 items-center gap-2.5">
                            <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-ink font-display text-xs text-paper">
                              {item.user_id.slice(0, 1).toUpperCase()}
                            </span>
                            <div className="min-w-0">
                              <div className="truncate text-sm font-medium text-ink">
                                {item.user_id}
                                {isSelf ? (
                                  <span className="ml-2 text-[11px] font-normal text-ink-ghost">
                                    （当前登录）
                                  </span>
                                ) : null}
                              </div>
                              <div className="mt-0.5 text-[11px] text-ink-ghost">
                                创建于 {item.created_at.slice(0, 10)}
                              </div>
                            </div>
                          </div>
                          <span
                            className={clsx(
                              "shrink-0 rounded-md px-2 py-0.5 text-[11px]",
                              ROLE_BADGE[item.role],
                            )}
                          >
                            {ROLE_LABELS[item.role]}
                          </span>
                        </div>
                        <div className="mt-3 flex gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            icon={<Pencil className="size-3.5" />}
                            onClick={() => {
                              setMode("edit");
                              setEditTarget(item);
                              setFormError(null);
                            }}
                          >
                            编辑
                          </Button>
                          <Button
                            size="sm"
                            variant="danger"
                            icon={<Trash2 className="size-3.5" />}
                            disabled={isSelf}
                            title={isSelf ? "不能删除自己" : undefined}
                            onClick={() => setPendingDelete(item)}
                          >
                            删除
                          </Button>
                        </div>
                      </>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </Modal>

      <ConfirmDialog
        open={pendingDelete !== null}
        title="删除用户"
        message={
          <>
            确定要删除用户「<span className="text-ink">{pendingDelete?.user_id}</span>」吗？
            <br />
            删除后该用户将立即无法登录，且不可恢复。
          </>
        }
        confirmText="删除"
        danger
        loading={deleteBusy}
        error={deleteError}
        onConfirm={handleDelete}
        onCancel={() => {
          setPendingDelete(null);
          setDeleteError(null);
        }}
      />
    </>
  );
}
