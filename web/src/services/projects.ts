/**
 * 项目 API 服务。
 *
 * POST   /api/projects        创建项目
 * GET    /api/projects        项目列表
 * GET    /api/projects/{id}   项目详情
 */

import { api } from "./api-client";

// ============================================================================
// 类型
// ============================================================================

export interface ProjectCreateRequest {
  title: string;
  input_type?: string; // natural_language | file_upload | template
  input_content?: string;
  audience?: string;
  difficulty?: string;
  constraints?: Record<string, unknown>;
}

export interface ProjectCreateResponse {
  id: string;
  title: string;
  status: string;
  created_at: string;
}

export interface ProjectListItem {
  id: string;
  title: string;
  topic: string | null;
  difficulty: string;
  status: string;
  frame_count: number;
  updated_at: string;
}

export interface ProjectListResponse {
  items: ProjectListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface ProjectDetailResponse {
  id: string;
  title: string;
  status: string;
  audience: string;
  difficulty: string;
  teaching_plan: Record<string, unknown> | null;
  knowledge_graph: Record<string, unknown> | null;
  dsl: Record<string, unknown> | null;
  quality_report: Record<string, unknown> | null;
  frame_count: number;
  created_at: string;
  updated_at: string;
}

// ============================================================================
// 方法
// ============================================================================

export function createProject(data: ProjectCreateRequest) {
  return api.post<ProjectCreateResponse>("/projects", data);
}

export function listProjects(params?: {
  page?: number;
  page_size?: number;
  status?: string;
}) {
  return api.get<ProjectListResponse>("/projects", params as Record<string, string>);
}

export function getProject(id: string) {
  return api.get<ProjectDetailResponse>(`/projects/${id}`);
}

export function deleteProject(id: string) {
  return api.delete<void>(`/projects/${id}`);
}