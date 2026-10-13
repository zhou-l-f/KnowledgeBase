import { http } from "@/api/client";
import type {
  CurrentUser,
  LoginRequest,
  TokenResponse,
  UserCreate,
  UserOut,
  UserUpdate,
} from "@/api/types";

export function login(payload: LoginRequest): Promise<TokenResponse> {
  return http.post<TokenResponse>("/auth/login", payload);
}

/** 当前登录用户（含角色），用于校验令牌有效性与控制界面显隐。 */
export function fetchMe(): Promise<CurrentUser> {
  return http.get<CurrentUser>("/auth/me");
}

// ---------------------------------------------------------------------------
// 用户管理：仅管理员可调用，非管理员会收到 403
// ---------------------------------------------------------------------------

export function listUsers(): Promise<UserOut[]> {
  return http.get<UserOut[]>("/auth/users");
}

export function createUser(payload: UserCreate): Promise<UserOut> {
  return http.post<UserOut>("/auth/users", payload);
}

export function updateUser(userId: string, payload: UserUpdate): Promise<UserOut> {
  return http.put<UserOut>(`/auth/users/${encodeURIComponent(userId)}`, payload);
}

export function deleteUser(userId: string): Promise<void> {
  return http.del<void>(`/auth/users/${encodeURIComponent(userId)}`);
}
