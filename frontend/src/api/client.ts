import { getToken } from "@/auth/token";

/** 统一的接口错误：status 为 HTTP 状态码，0 表示网络层失败。 */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

type UnauthorizedHandler = () => void;

let onUnauthorized: UnauthorizedHandler | null = null;

/** 注册 401 全局处理器（令牌失效时由 AuthProvider 触发登出）。 */
export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  onUnauthorized = handler;
}

/** 从 FastAPI 错误体中提取可读信息：detail 既可能是字符串，也可能是校验错误数组。 */
function extractDetail(payload: unknown): string | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => (item && typeof item === "object" ? (item as { msg?: unknown }).msg : null))
      .filter((msg): msg is string => typeof msg === "string");
    if (messages.length > 0) {
      return messages.join("；");
    }
  }
  return null;
}

async function parseBody(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

/** 请求基址为空：开发期由 Vite 代理转发到后端，保持同源、无需 CORS。 */
export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  const token = getToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let res: Response;
  try {
    res = await fetch(path, { ...options, headers });
  } catch {
    throw new ApiError(0, "无法连接服务器，请确认后端服务已启动");
  }

  if (res.status === 401) {
    onUnauthorized?.();
  }

  if (res.status === 204) {
    return undefined as T;
  }

  const payload = await parseBody(res);
  if (!res.ok) {
    throw new ApiError(res.status, extractDetail(payload) ?? `请求失败（HTTP ${res.status}）`);
  }
  return payload as T;
}

function jsonBody(body: unknown): string | undefined {
  return body === undefined ? undefined : JSON.stringify(body);
}

export const http = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: jsonBody(body) }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PUT", body: jsonBody(body) }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  postForm: <T>(path: string, form: FormData) =>
    request<T>(path, { method: "POST", body: form }),
};

/** 拉取二进制内容（媒体附件需携带令牌，无法直接用 <img src>）。 */
export async function fetchBlob(path: string): Promise<Blob> {
  const headers = new Headers();
  const token = getToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  let res: Response;
  try {
    res = await fetch(path, { headers });
  } catch {
    throw new ApiError(0, "无法连接服务器，请确认后端服务已启动");
  }
  if (res.status === 401) {
    onUnauthorized?.();
  }
  if (!res.ok) {
    throw new ApiError(res.status, `资源加载失败（HTTP ${res.status}）`);
  }
  return res.blob();
}
