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
  affects_frame_ids?: string[];
}

export interface ParameterListResponse {
  parameters: ParameterData[];
}

export interface RecomputeImpact {
  mode: "local" | "partial_frames" | "all_frames";
  scope: { type: string; frame_ids: string[] } | null;
  changed_keys: string[];
  dependencies: Record<string, string[]>;
  direct_frame_ids: string[];
  affected_frame_ids: string[];
  affected_module_ids?: string[];
  module_dependencies?: Record<string, string[]>;
  protected_frame_ids: string[];
  fallback_used: boolean;
  reason: string;
  impact_token: string;
}

// ============================================================================
// 方法
// ============================================================================

export function listParameters(projectId: string) {
  return api.get<ParameterListResponse>(`/projects/${projectId}/parameters`);
}

export function recomputeProject(projectId: string, changedParams: Record<string, unknown>, expectedImpactToken?: string) {
  return api.post<RecomputeImpact & { stream_url: string | null }>(`/projects/${projectId}/recompute`, {
    changed_params: changedParams,
    expected_impact_token: expectedImpactToken,
  });
}

export function previewRecomputeProject(projectId: string, changedParams: Record<string, unknown>) {
  return api.post<RecomputeImpact>(`/projects/${projectId}/recompute/preview`, {
    changed_params: changedParams,
  });
}
