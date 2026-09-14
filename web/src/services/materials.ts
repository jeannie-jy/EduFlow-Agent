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
