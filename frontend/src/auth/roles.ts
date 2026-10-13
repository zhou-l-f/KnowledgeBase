import type { Role } from "@/api/types";

/** 角色中文标签。 */
export const ROLE_LABELS: Record<Role, string> = {
  admin: "管理员",
  editor: "编辑",
  readonly: "只读",
};

export function roleLabel(role: Role | null | undefined): string {
  return role ? ROLE_LABELS[role] : "未登录";
}

/** 内容写权限：管理员 / 编辑（与后端 CONTENT_WRITE_ROLES 保持一致）。 */
export function canWrite(role: Role | null | undefined): boolean {
  return role === "admin" || role === "editor";
}

/** 管理员权限：用户管理。 */
export function isAdmin(role: Role | null | undefined): boolean {
  return role === "admin";
}
