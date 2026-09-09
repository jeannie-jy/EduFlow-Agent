/**
 * 版本管理 API 服务。
 *
 * POST   /api/projects/{id}/versions                    保存版本
 * GET    /api/projects/{id}/versions                     版本列表
 * GET    /api/projects/{id}/versions/{vid}               获取指定版本 DSL
 * POST   /api/projects/{id}/versions/{vid}/restore       恢复版本
 */

import { api } from "./api-client";

// ============================================================================
// 类型
// ============================================================================

export interface VersionItem {
  id: string;
  version: number;
  change_summary: string;
  created_at: string;
  is_current?: boolean;
}

export interface VersionListResponse {
  versions: VersionItem[];
}

export interface CreateVersionRequest {
  change_summary: string;
}

export interface CreateVersionResponse {
  version: number;
  id: string;
}

export interface RestoreVersionResponse {
  restored_to_version: number;
  id: string;
}

// ============================================================================
// 方法
// ============================================================================

export interface VersionDetailResponse {
  id: string;
  version: number;
  change_summary: string;
  dsl: Record<string, unknown>;
  created_at: string;
  is_current?: boolean;
}

export interface VersionDiffResponse {
  from: { type: "version"; id: string; version: number };
  to: { type: "current" | "version"; id: string; version?: number };
  summary: {
    frames_added: number;
    frames_removed: number;
    frames_modified: number;
    parameters_changed: number;
    metadata_fields_changed: number;
    frame_order_changed: boolean;
  };
  frames: {
    added: string[];
    removed: string[];
    modified: Array<{ frame_id: string; changed_fields: string[] }>;
    order_changed: boolean;
  };
  parameters: Array<{ key: string; change: "added" | "removed" | "modified" }>;
  metadata_changed: string[];
}

export function saveVersion(projectId: string, changeSummary: string) {
  return api.post<CreateVersionResponse>(`/projects/${projectId}/versions`, {
    change_summary: changeSummary,
  } as CreateVersionRequest);
}

export function listVersions(projectId: string) {
  return api.get<VersionListResponse>(`/projects/${projectId}/versions`);
}

export function getVersion(projectId: string, versionId: string) {
  return api.get<VersionDetailResponse>(`/projects/${projectId}/versions/${versionId}`);
}

export function restoreVersion(projectId: string, versionId: string) {
  return api.post<RestoreVersionResponse>(`/projects/${projectId}/versions/${versionId}/restore`);
}

export function diffVersion(projectId: string, versionId: string, toVersionId?: string) {
  const query = toVersionId ? `?to_version_id=${encodeURIComponent(toVersionId)}` : "";
  return api.get<VersionDiffResponse>(`/projects/${projectId}/versions/${versionId}/diff${query}`);
}
