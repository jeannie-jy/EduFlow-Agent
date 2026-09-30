/**
 * 课件材料 API。
 *
 * 上传后由后台异步解析，项目生成时只会使用用户明确选入的材料。
 */

import { api } from "./api-client";

export type MaterialStatus = "uploaded" | "parse_queued" | "parsed" | "parse_failed";

export interface MaterialItem {
  id: string;
  filename: string;
  type: string;
  size_bytes: number;
  status: MaterialStatus;
  is_library?: boolean;
  created_at?: string;
}

export interface MaterialUploadResponse {
  id: string;
  filename: string;
  type: string;
  size_bytes: number;
}

export interface MaterialParseResponse {
  id: string;
  status: string;
  job_id: string | null;
  status_url: string | null;
  parsed_result: Record<string, unknown> | null;
}

export interface BackgroundJobResponse {
  job_id: string;
  kind: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  attempt_count: number;
  error_code: string | null;
}

export interface LibraryMaterialItem {
  id: string;
  filename: string;
  parse_status: string;
  index_status: "draft" | "published" | "retired";
  job_status: "queued" | "running" | "completed" | "failed" | null;
  index_error: string | null;
  size_bytes: number;
}

export interface MaterialIndexStatus {
  id: string;
  status: "not_requested" | "queued" | "running" | "completed" | "failed";
  job_id: string | null;
  error_class: string | null;
  attempt_count: number;
  source_status: string | null;
}

export function listTeacherLibrary() {
  return api.get<{ items: LibraryMaterialItem[] }>("/materials/library");
}

export function enableTeacherLibrary(id: string) {
  return api.post<{ material_id: string; source_id: string }>(`/materials/${id}/library`);
}

export function queueMaterialIndex(id: string) {
  return api.post<MaterialIndexStatus>(`/materials/${id}/index`);
}

export function getMaterialIndexStatus(id: string) {
  return api.get<MaterialIndexStatus>(`/materials/${id}/index`);
}

export function retryMaterialIndex(id: string) {
  return api.post<MaterialIndexStatus>(`/materials/${id}/index/retry`);
}

export function listProjectLibraryMaterials(projectId: string) {
  return api.get<{ items: Array<{ material_id: string; filename: string; source_id: string; index_status: string }> }>(
    `/materials/projects/${projectId}`,
  );
}

export function attachLibraryMaterial(id: string, projectId: string) {
  return api.put(`/materials/${id}/projects/${projectId}`);
}

export function detachLibraryMaterial(id: string, projectId: string) {
  return api.delete(`/materials/${id}/projects/${projectId}`);
}

export function listMaterials() {
  return api.get<{ items: MaterialItem[] }>("/materials");
}

export function uploadMaterial(file: File) {
  return api.upload<MaterialUploadResponse>("/materials/upload", file, 120_000);
}

export function parseMaterial(id: string) {
  return api.post<MaterialParseResponse>(`/materials/${id}/parse`);
}

export function getBackgroundJob(id: string) {
  return api.get<BackgroundJobResponse>(`/background-jobs/${id}`);
}

export function deleteMaterial(id: string) {
  return api.delete<void>(`/materials/${id}`);
}
