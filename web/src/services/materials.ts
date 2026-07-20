/**
 * 素材 API 服务。
 *
 * POST   /api/materials/upload         上传课件文件
 * POST   /api/materials/{id}/parse     解析为结构化内容
 * GET    /api/materials/{id}/preview   预览解析结果
 */

import { api } from "./api-client";

// ============================================================================
// 类型
// ============================================================================

export interface MaterialUploadResponse {
  id: string;
  filename: string;
  type: string;
  size_bytes: number;
}

export interface MaterialParseResponse {
  id: string;
  status: string;
  parsed_result: {
    topics: string[];
    raw_text: string;
  } | null;
}

export interface MaterialPreviewResponse {
  id: string;
  filename: string;
  type: string;
  size_bytes: number;
  preview: string;
}

// ============================================================================
// 方法
// ============================================================================

export function uploadMaterial(file: File) {
  return api.upload<MaterialUploadResponse>("/materials/upload", file);
}

export function parseMaterial(materialId: string) {
  return api.post<MaterialParseResponse>(`/materials/${materialId}/parse`);
}

export function previewMaterial(materialId: string) {
  return api.get<MaterialPreviewResponse>(`/materials/${materialId}/preview`);
}