/**
 * 反馈 API 服务。
 *
 * GET    /api/projects/{id}/feedback    查询反馈列表
 * POST   /api/projects/{id}/feedback    提交反馈
 */

import { api } from "./api-client";

// ============================================================================
// 类型
// ============================================================================

export interface FeedbackItem {
  id: string;
  frame_id: string | null;
  type: "rating" | "correction" | "suggestion";
  content: string;
  rating: number | null;
  resolved: boolean;
  created_at: string;
}

export interface FeedbackListResponse {
  items: FeedbackItem[];
}

export interface FeedbackRequest {
  frame_id?: string;
  type: "rating" | "correction" | "suggestion";
  content: string;
  rating?: number; // 1-5, type=rating 时必填
}

export interface FeedbackResponse {
  id: string;
}

// ============================================================================
// 方法
// ============================================================================

export function listFeedback(projectId: string) {
  return api.get<FeedbackListResponse>(`/projects/${projectId}/feedback`);
}

export function submitFeedback(projectId: string, data: FeedbackRequest) {
  return api.post<FeedbackResponse>(`/projects/${projectId}/feedback`, data);
}