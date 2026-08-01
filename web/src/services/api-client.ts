/**
 * API 客户端 — 基于 fetch 的统一 HTTP 请求封装。
 *
 * - 自动拼接 VITE_API_BASE_URL 前缀
 * - 统一的错误模型（ApiError）
 * - 请求/响应拦截
 * - 超时控制
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

// ============================================================================
// 类型
// ============================================================================

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
}

export class ApiError extends Error {
  code: string;
  status: number;
  details?: unknown;

  constructor(status: number, body: ApiErrorBody) {
    super(body.error.message);
    this.name = "ApiError";
    this.code = body.error.code;
    this.status = status;
    this.details = body.error.details;
  }
}

export class NetworkError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "NetworkError";
  }
}

export class TimeoutError extends Error {
  constructor(ms: number) {
    super(`请求超时（${ms}ms）`);
    this.name = "TimeoutError";
  }
}

// ============================================================================
// 核心请求方法
// ============================================================================

const DEFAULT_TIMEOUT_MS = 30_000;

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  options?: { timeoutMs?: number; params?: Record<string, string> },
): Promise<T> {
  const url = buildUrl(path, options?.params);
  const timeoutMs = options?.timeoutMs ?? DEFAULT_TIMEOUT_MS;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  const headers: Record<string, string> = {};
  if (body !== undefined && !(body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  try {
    const res = await fetch(url, {
      method,
      headers,
      body: body instanceof FormData ? body : body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });

    if (!res.ok) {
      let errorBody: ApiErrorBody;
      try {
        errorBody = await res.json();
      } catch {
        throw new ApiError(res.status, {
          error: { code: "UNKNOWN", message: `HTTP ${res.status}: ${res.statusText}` },
        });
      }
      throw new ApiError(res.status, errorBody);
    }

    // 204 No Content
    if (res.status === 204) return undefined as T;

    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if ((err as Error).name === "AbortError") {
      throw new TimeoutError(timeoutMs);
    }
    throw new NetworkError((err as Error).message ?? "网络请求失败");
  } finally {
    clearTimeout(timer);
  }
}

function buildUrl(path: string, params?: Record<string, string>): string {
  const url = new URL(BASE_URL + path, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null) url.searchParams.set(k, v);
    });
  }
  return url.toString();
}

// ============================================================================
// 公开方法
// ============================================================================

export const api = {
  get<T>(path: string, params?: Record<string, string>, timeoutMs?: number) {
    return request<T>("GET", path, undefined, { params, timeoutMs });
  },

  post<T>(path: string, body?: unknown, timeoutMs?: number) {
    return request<T>("POST", path, body, { timeoutMs });
  },

  put<T>(path: string, body?: unknown, timeoutMs?: number) {
    return request<T>("PUT", path, body, { timeoutMs });
  },

  delete<T>(path: string, timeoutMs?: number) {
    return request<T>("DELETE", path, undefined, { timeoutMs });
  },

  /**
   * 上传文件（multipart/form-data）
   */
  upload<T>(path: string, file: File, timeoutMs?: number) {
    const form = new FormData();
    form.append("file", file);
    return request<T>("POST", path, form, { timeoutMs });
  },

  /**
   * 获取原始 fetch 响应用于 SSE 流式消费
   */
  async stream(path: string, body?: unknown, signal?: AbortSignal): Promise<Response> {
    const url = buildUrl(path);
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };

    const res = await fetch(url, {
      method: "POST",
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal,
    });

    if (!res.ok) {
      let errorBody: ApiErrorBody;
      try {
        errorBody = await res.json();
      } catch {
        throw new ApiError(res.status, {
          error: { code: "UNKNOWN", message: `HTTP ${res.status}: ${res.statusText}` },
        });
      }
      throw new ApiError(res.status, errorBody);
    }

    return res;
  },
};