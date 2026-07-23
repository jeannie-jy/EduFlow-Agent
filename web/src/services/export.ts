/**
 * 导出 API 服务。
 *
 * POST   /api/projects/{id}/export/manim           创建视频导出
 * GET    /api/export/{job_id}                      查询导出状态
 * GET    /api/export/{job_id}/download/{filename}  下载产物
 */

import { api } from "./api-client";

// ============================================================================
// 类型
// ============================================================================

export interface ExportManimRequest {
  quality?: "l" | "m" | "h" | "k"; // 480p / 720p / 1080p / 4K
  format?: string;
  fps?: number;
  include_subtitles?: boolean;
  include_tts?: boolean;
}

export interface ExportCreateResponse {
  job_id: string;
  status: string;
}

export interface ExportArtifact {
  type: string; // mp4 / manim_source / subtitle
  url: string;
  size_bytes: number;
}

export interface ExportJobResponse {
  job_id: string;
  status: "queued" | "rendering" | "completed" | "failed";
  progress_pct: number;
  artifacts: ExportArtifact[] | null;
  error_log: string | null;
  duration_ms: number | null;
  total_frames: number | null;
}

// ============================================================================
// 方法
// ============================================================================

export function createExportJob(projectId: string, config: ExportManimRequest = {}) {
  return api.post<ExportCreateResponse>(`/projects/${projectId}/export/manim`, {
    quality: config.quality ?? "h",
    format: config.format ?? "mp4",
    fps: config.fps ?? 30,
    include_subtitles: config.include_subtitles ?? true,
    include_tts: config.include_tts ?? false,
  } as ExportManimRequest);
}

export function getExportStatus(jobId: string) {
  return api.get<ExportJobResponse>(`/export/${jobId}`);
}