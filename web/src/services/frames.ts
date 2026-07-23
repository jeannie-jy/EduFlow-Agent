/**
 * 帧 API 服务。
 *
 * GET    /api/projects/{id}/frames             帧列表
 * PUT    /api/projects/{id}/frames/{fid}       编辑单帧
 * POST   /api/projects/{id}/frames/{fid}/lock  锁定/解锁帧
 */

import { api } from "./api-client";

// ============================================================================
// 类型
// ============================================================================

export interface FrameData {
  id: string;
  frame_id: string;
  order_index: number;
  title: string;
  narration: string;
  visual_objects: Record<string, unknown>[];
  state_snapshot: Record<string, unknown>;
  animations: Record<string, unknown>[];
  interaction_hooks: Record<string, unknown>[];
  quality_status: string;
  is_locked: boolean;
}

export interface FrameListResponse {
  frames: FrameData[];
  version: number;
}

export interface FrameUpdateRequest {
  title?: string;
  narration?: string;
  visual_objects?: Record<string, unknown>[];
  state_snapshot?: Record<string, unknown>;
  animations?: Record<string, unknown>[];
}

export interface FrameLockRequest {
  is_locked: boolean;
}

// ============================================================================
// 方法
// ============================================================================

export function listFrames(projectId: string, version?: number) {
  return api.get<FrameListResponse>(`/projects/${projectId}/frames`, {
    version: version?.toString() ?? "1",
  });
}

export function updateFrame(projectId: string, frameId: string, data: FrameUpdateRequest) {
  return api.put<{ id: string; updated_at: string }>(
    `/projects/${projectId}/frames/${frameId}`,
    data,
  );
}

export function lockFrame(projectId: string, frameId: string, isLocked: boolean) {
  return api.post<{ id: string; is_locked: boolean }>(
    `/projects/${projectId}/frames/${frameId}/lock`,
    { is_locked: isLocked } as FrameLockRequest,
  );
}