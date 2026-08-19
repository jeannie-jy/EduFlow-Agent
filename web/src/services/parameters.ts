/**
 * 参数 API 服务。
 *
 * GET    /api/projects/{id}/parameters    参数列表
 * POST   /api/projects/{id}/recompute     参数变更并重算
 */

import { api } from "./api-client";

// ============================================================================
// 类型
// ============================================================================

export interface ParameterData {
  id: string;
  key: string;
  label: string;
  param_type: string;
  default_value: unknown;
  current_value: unknown;
  constraints: Record<string, unknown>;
  recompute_scope: string; // "local" | "all_frames"
}

export interface ParameterListResponse {
  parameters: ParameterData[];
}

// ============================================================================
// 方法
// ============================================================================

export function listParameters(projectId: string) {
  return api.get<ParameterListResponse>(`/projects/${projectId}/parameters`);
}

export function recomputeProject(projectId: string, changedParams: Record<string, unknown>) {
  return api.post<{ stream_url: string }>(`/projects/${projectId}/recompute`, {
    changed_params: changedParams,
  });
}
