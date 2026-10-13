/**
 * 令牌存储：登录成功后保存 JWT，请求时由 API client 注入 Authorization 头。
 * 使用 localStorage 以支持刷新后保持登录态。
 */

const TOKEN_KEY = "kb.access_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}
