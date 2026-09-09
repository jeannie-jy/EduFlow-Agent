/**
 * 生成流程 API 服务。
 *
 * POST   /api/projects/{id}/generate           启动生成
 * GET    /api/projects/{id}/generate/stream     SSE 进度流
 * POST   /api/projects/{id}/regenerate         局部重生成
 */

import { api } from "./api-client";
import { connectSSE, type SSEOptions } from "./sse";

// ============================================================================
// 类型
// ============================================================================

export interface GenerateRequest {
  action?: "full" | "plan_only" | "modules";
  modules?: string[];
}

export interface GenerateResponse {
  stream_url: string;
}

export interface ActiveStreamResponse {
  stream_url: string | null;
  stream_id?: string;
  kind?: string;
  last_event_id?: number;
  created_at?: string;
}

export interface ModuleInfo {
  module_id: string;
  display_name: string;
  description: string;
  icon: string;
  category: "visual" | "interactive" | "export";
  priority: number;
  estimated_seconds: number;
}

export interface ModuleSelectRequest {
  modules: string[];
}

export interface ModuleCostEstimate {
  available: boolean;
  requested_module_count: number;
  estimated_cost_usd: number | null;
  sample_count: number;
  method: "historical_median_per_module" | "unavailable";
  hard_limit_cost_usd: number;
  hard_limit_tokens: number;
}

export interface ApprovePlanRequest {
  modules?: string[];
}

export interface RegenerateRequest {
  scope: {
    type: "single_frame" | "frame_range" | "from_frame" | "all_frames";
    frame_ids?: string[];
  };
}

type ActiveStreamSession = {
  url: string;
  lastEventId?: string;
  savedAt: number;
};

const activeStreamKey = (projectId: string) => `eduflow:active-stream:${projectId}`;

function projectIdFromStreamUrl(url: string): string | null {
  const match = url.match(/\/projects\/([^/]+)\//);
  return match ? decodeURIComponent(match[1]) : null;
}

function storeActiveStream(projectId: string, session: ActiveStreamSession) {
  if (typeof window === "undefined" || /[?&]feedback=/.test(session.url)) return;
  try {
    window.sessionStorage.setItem(activeStreamKey(projectId), JSON.stringify(session));
  } catch { /* Storage may be disabled by browser policy. */ }
}

function updateActiveStreamCursor(projectId: string, url: string, event: unknown) {
  const eventId = (event as Record<string, unknown>)?.event_id;
  if (eventId === undefined || eventId === null) return;
  storeActiveStream(projectId, { url, lastEventId: String(eventId), savedAt: Date.now() });
}

function clearActiveStream(projectId: string, url: string) {
  if (typeof window === "undefined") return;
  try {
    const raw = window.sessionStorage.getItem(activeStreamKey(projectId));
    const current = raw ? JSON.parse(raw) as ActiveStreamSession : null;
    if (!current || current.url === url) window.sessionStorage.removeItem(activeStreamKey(projectId));
  } catch { /* Ignore malformed or unavailable session storage. */ }
}

// ============================================================================
// 方法
// ============================================================================

export function startGeneration(projectId: string, action: GenerateRequest["action"] = "full", modules?: string[]) {
  const body: GenerateRequest = { action };
  if (modules !== undefined) body.modules = modules;
  return api.post<GenerateResponse>(`/projects/${projectId}/generate`, body);
}

export function streamGeneration(projectId: string, options: SSEOptions) {
  const baseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";
  return streamFromUrl(
    `${baseUrl}/projects/${projectId}/generate/stream?stream_id=${crypto.randomUUID()}`,
    options,
  );
}

/**
 * 从后端返回的 stream_url（形如 "/api/projects/.../generate/resume/stream?..."）连接 SSE。
 * 用于 HITL 审批的 resume 流。stream_url 已含 /api 前缀，需用 origin 拼接而非 VITE_API_BASE_URL。
 */
export function streamFromUrl(streamUrl: string, options: SSEOptions) {
  const baseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";
  // baseUrl 形如 http://host/api —— 取其 origin 再拼后端返回的绝对路径
  const origin = baseUrl.replace(/\/api\/?$/, "");
  const url = streamUrl.startsWith("http") ? streamUrl : `${origin}${streamUrl}`;
  const projectId = projectIdFromStreamUrl(url);
  if (projectId) storeActiveStream(projectId, {
    url,
    lastEventId: options.lastEventId,
    savedAt: Date.now(),
  });
  const wrapped: SSEOptions = projectId ? {
    ...options,
    onProgress: (event) => { updateActiveStreamCursor(projectId, url, event); options.onProgress?.(event); },
    onWaitingApproval: (event) => { updateActiveStreamCursor(projectId, url, event); clearActiveStream(projectId, url); options.onWaitingApproval?.(event); },
    onDone: (event) => { updateActiveStreamCursor(projectId, url, event); clearActiveStream(projectId, url); options.onDone?.(event); },
    onError: (event) => {
      updateActiveStreamCursor(projectId, url, event);
      if ((event as unknown as Record<string, unknown>).event_id != null) clearActiveStream(projectId, url);
      options.onError?.(event);
    },
    onModuleStart: (event) => { updateActiveStreamCursor(projectId, url, event); options.onModuleStart?.(event); },
    onModuleDone: (event) => { updateActiveStreamCursor(projectId, url, event); options.onModuleDone?.(event); },
    onModuleError: (event) => { updateActiveStreamCursor(projectId, url, event); options.onModuleError?.(event); },
  } : options;
  return connectSSE(url, wrapped);
}

export function resumeProjectStream(projectId: string, options: SSEOptions) {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(activeStreamKey(projectId));
    if (!raw) return null;
    const session = JSON.parse(raw) as ActiveStreamSession;
    if (!session.url || Date.now() - session.savedAt > 24 * 60 * 60 * 1000) {
      window.sessionStorage.removeItem(activeStreamKey(projectId));
      return null;
    }
    return streamFromUrl(session.url, {
      ...options,
      lastEventId: session.lastEventId ?? options.lastEventId,
    });
  } catch {
    window.sessionStorage.removeItem(activeStreamKey(projectId));
    return null;
  }
}

/** Recover from the server ledger when this browser has no local stream cursor. */
export async function discoverProjectStream(projectId: string, options: SSEOptions) {
  const active = await api.get<ActiveStreamResponse>(
    `/projects/${projectId}/generate/active-stream`,
  );
  if (!active.stream_url) return null;
  return streamFromUrl(active.stream_url, {
    ...options,
    lastEventId: active.last_event_id
      ? String(active.last_event_id)
      : options.lastEventId,
  });
}

export function regenerate(projectId: string, scope: RegenerateRequest["scope"]) {
  return api.post<GenerateResponse>(`/projects/${projectId}/regenerate`, {
    scope,
  } as RegenerateRequest);
}

// ============================================================================
// 模块生成（Phase A）
// ============================================================================

/** 获取可用模块列表 */
export function listModules(projectId: string) {
  return api.get<{ modules: ModuleInfo[] }>(`/projects/${projectId}/generate/modules`);
}

/** 提交模块选择，开始生成 */
export function startModuleGeneration(projectId: string, modules: string[]) {
  return api.post<GenerateResponse>(`/projects/${projectId}/generate/modules`, {
    modules,
  } as ModuleSelectRequest);
}

/** 连接模块生成 SSE 流 */
export function streamModuleGeneration(projectId: string, options: SSEOptions) {
  const baseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";
  return streamFromUrl(
    `${baseUrl}/projects/${projectId}/generate/modules/stream?stream_id=${crypto.randomUUID()}`,
    options,
  );
}

export function estimateModuleCost(projectId: string, modules: string[]) {
  return api.post<ModuleCostEstimate>(
    `/projects/${projectId}/generate/modules/cost-estimate`,
    { modules } as ModuleSelectRequest,
  );
}

/** Persist a bounded module batch and connect to the exact stream returned by the API. */
export async function regenerateModules(projectId: string, modules: string[], options: SSEOptions) {
  const generation = await startModuleGeneration(projectId, modules);
  return streamFromUrl(generation.stream_url, options);
}

// ============================================================================
// HITL 审批
// ============================================================================

export interface ApprovePlanResponse {
  stream_url: string;
  available_modules?: ModuleInfo[];
}

export function approvePlan(projectId: string, modules?: string[]) {
  return api.post<ApprovePlanResponse>(`/projects/${projectId}/generate/approve`, {
    modules: modules ?? null,
  } as ApprovePlanRequest);
}

export function rejectPlan(projectId: string, feedback: string) {
  return api.post<GenerateResponse>(`/projects/${projectId}/generate/reject`, {
    feedback,
  });
}

// ============================================================================
// 单模块重新生成（Phase F）
// ============================================================================

/** 重新生成单个模块（SSE 流） */
export function regenerateModule(projectId: string, moduleId: string, options: SSEOptions) {
  const baseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";
  return streamFromUrl(
    `${baseUrl}/projects/${projectId}/generate/module/${moduleId}/stream?stream_id=${crypto.randomUUID()}`,
    options,
  );
}
