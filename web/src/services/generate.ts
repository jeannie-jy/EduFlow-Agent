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

export interface ApprovePlanRequest {
  modules?: string[];
}

export interface RegenerateRequest {
  scope: {
    type: "single_frame" | "frame_range" | "from_frame";
    frame_ids?: string[];
    locked_frame_ids?: string[];
  };
}

// ============================================================================
// 方法
// ============================================================================

export function startGeneration(projectId: string, action: GenerateRequest["action"] = "full") {
  return api.post<GenerateResponse>(`/projects/${projectId}/generate`, {
    action,
  } as GenerateRequest);
}

export function streamGeneration(projectId: string, options: SSEOptions) {
  const baseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";
  return connectSSE(`${baseUrl}/projects/${projectId}/generate/stream`, options);
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
  return connectSSE(url, options);
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
  return connectSSE(`${baseUrl}/projects/${projectId}/generate/modules/stream`, options);
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