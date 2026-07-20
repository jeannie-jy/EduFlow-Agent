/**
 * 导出中心 — Manim 视频导出配置 + 任务队列 + 下载。
 *
 * 对接: POST /api/projects/{id}/export/manim, GET /api/export/{job_id}
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  ArrowLeft,
  Film,
  Download,
  AlertCircle,
  CheckCircle2,
} from "lucide-react";
import { Link } from "react-router-dom";
import {
  createExportJob,
  getExportStatus,
  type ExportJobResponse,
  ApiError,
  NetworkError,
} from "@/services";

const statusLabels: Record<string, string> = {
  queued: "排队中",
  rendering: "渲染中",
  completed: "已完成",
  failed: "失败",
};

const statusColors: Record<string, string> = {
  queued: "bg-slate-100 text-slate-600",
  rendering: "bg-indigo-100 text-indigo-600",
  completed: "bg-green-100 text-green-600",
  failed: "bg-red-100 text-red-600",
};

export function ExportCenter() {
  const { projectId } = useParams<{ projectId: string }>();
  const [quality, setQuality] = useState("h");
  const [fps, setFps] = useState("30");
  const [includeSubtitles, setIncludeSubtitles] = useState("true");
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<ExportJobResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const pollRef = useRef<ReturnType<typeof setInterval>>();

  const startPolling = useCallback((id: string) => {
    pollRef.current = setInterval(async () => {
      try {
        const status = await getExportStatus(id);
        setJob(status);
        if (status.status === "completed" || status.status === "failed") {
          clearInterval(pollRef.current);
        }
      } catch {
        // 轮询失败静默处理
      }
    }, 3000);
  }, []);

  useEffect(() => {
    return () => clearInterval(pollRef.current);
  }, []);

  const handleCreate = async () => {
    if (!projectId) return;
    setSubmitting(true);
    setError("");
    try {
      const res = await createExportJob(projectId, {
        quality: quality as "l" | "m" | "h" | "k",
        fps: parseInt(fps, 10),
        include_subtitles: includeSubtitles === "true",
      });
      setJobId(res.job_id);
      startPolling(res.job_id);
    } catch (err) {
      if (err instanceof NetworkError) setError("无法连接到服务器");
      else if (err instanceof ApiError) setError(err.message);
      else setError("创建导出任务失败");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl p-6">
      <Link
        to="/app"
        className="mb-6 inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700"
      >
        <ArrowLeft size={17} />
        返回工作台
      </Link>

      <h1 className="text-2xl font-bold text-slate-900 mb-2">导出中心</h1>
      <p className="text-sm text-slate-500 mb-8">将推演导出为 Manim 教学视频</p>

      {/* 配置表单 */}
      {!jobId && (
        <div className="rounded-xl border border-slate-200 bg-white p-6 space-y-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>画质</Label>
              <Select value={quality} onValueChange={(v) => setQuality(v ?? "h")}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="l">480p (流畅)</SelectItem>
                  <SelectItem value="m">720p (高清)</SelectItem>
                  <SelectItem value="h">1080p (全高清)</SelectItem>
                  <SelectItem value="k">4K (超高清)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="fps">帧率 (FPS)</Label>
              <Input
                id="fps"
                type="number"
                value={fps}
                onChange={(e) => setFps(e.target.value)}
                min={15}
                max={60}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label>字幕</Label>
            <Select value={includeSubtitles} onValueChange={(v) => setIncludeSubtitles(v ?? "true")}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="true">包含字幕</SelectItem>
                <SelectItem value="false">不含字幕</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {error && (
            <div className="flex items-center gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-600">
              <AlertCircle size={16} />
              {error}
            </div>
          )}

          <Button onClick={handleCreate} disabled={submitting} className="w-full gap-2">
            <Film size={18} />
            {submitting ? "正在创建..." : "开始导出"}
          </Button>
        </div>
      )}

      {/* 任务状态 */}
      {job && (
        <div className="rounded-xl border border-slate-200 bg-white p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-slate-900">导出任务</h3>
            <Badge className={statusColors[job.status] ?? ""}>
              {statusLabels[job.status] ?? job.status}
            </Badge>
          </div>

          <Progress value={job.progress_pct} className="h-2" />
          <p className="text-right text-xs text-slate-400">{job.progress_pct.toFixed(0)}%</p>

          {job.status === "failed" && job.error_log && (
            <div className="rounded-lg bg-red-50 p-3 text-sm text-red-600">
              {job.error_log}
            </div>
          )}

          {job.status === "completed" && job.artifacts && (
            <div className="space-y-2">
              <p className="text-sm font-medium text-green-700 flex items-center gap-2">
                <CheckCircle2 size={16} /> 导出完成
              </p>
              {job.artifacts.map((artifact) => (
                <a
                  key={artifact.type}
                  href={artifact.url}
                  download
                  className="flex items-center justify-between rounded-lg border border-slate-200 p-3 hover:bg-slate-50 transition-colors"
                >
                  <span className="text-sm font-medium text-slate-700">
                    {artifact.type === "mp4" ? "视频文件" : artifact.type === "manim_source" ? "Manim 源码" : "字幕文件"}
                  </span>
                  <span className="flex items-center gap-2 text-xs text-slate-400">
                    {artifact.size_bytes > 0 ? `${(artifact.size_bytes / 1048576).toFixed(1)} MB` : ""}
                    <Download size={16} />
                  </span>
                </a>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}