import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Captions,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Download,
  Film,
  LoaderCircle,
  Mic2,
  MonitorPlay,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { VisualObjectRenderer } from "@/components/workbench/visual-objects/VisualObjectRenderer";
import { cn } from "@/lib/utils";
import { toUserFacingError } from "@/lib/user-facing-error";
import { createExportJob, getExportStatus, type ExportArtifact, type ExportManimRequest } from "@/services/export";
import { normalizeFramesArtifact, normalizeVideoArtifact } from "./artifact-model";

const qualityOptions = [
  { value: "l", label: "480p", note: "快速" },
  { value: "m", label: "720p", note: "标准" },
  { value: "h", label: "1080p", note: "高清" },
  { value: "k", label: "4K", note: "超清" },
] as const;

const fpsOptions = [24, 30, 60] as const;

function formatFileSize(value: number) {
  if (!value) return "";
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

export function VideoStudioCard({
  videoValue,
  framesValue,
  projectId,
  targetFrameId,
}: {
  videoValue: unknown;
  framesValue: unknown;
  projectId?: string;
  targetFrameId?: string;
}) {
  const video = useMemo(() => normalizeVideoArtifact(videoValue), [videoValue]);
  const frames = useMemo(() => normalizeFramesArtifact(framesValue), [framesValue]);
  const [status, setStatus] = useState(video.status ?? "idle");
  const [progress, setProgress] = useState(0);
  const [artifacts, setArtifacts] = useState<ExportArtifact[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [jobId, setJobId] = useState(video.job_id);
  const [config, setConfig] = useState<ExportManimRequest>({
    quality: (video.config?.quality as ExportManimRequest["quality"]) ?? "h",
    format: String(video.config?.format ?? "mp4"),
    fps: Number(video.config?.fps ?? 30),
    include_subtitles: video.config?.include_subtitles !== false,
    include_tts: video.config?.include_tts === true,
  });
  const [creatingJob, setCreatingJob] = useState(false);
  const [sourceFramesVersion, setSourceFramesVersion] = useState(video.source_frames_version);
  const [selectedFrameIndex, setSelectedFrameIndex] = useState(0);

  useEffect(() => {
    if (!jobId) return;
    let cancelled = false;
    let timeout: number | undefined;
    const poll = async () => {
      try {
        const result = await getExportStatus(jobId);
        if (cancelled) return;
        setStatus(result.status);
        setProgress(result.progress_pct ?? 0);
        setArtifacts(result.artifacts ?? []);
        if (result.status === "failed") setError(result.error_log ?? "渲染失败");
        if (result.status !== "completed" && result.status !== "failed") {
          timeout = window.setTimeout(poll, 3000);
        }
      } catch {
        if (!cancelled) timeout = window.setTimeout(poll, 5000);
      }
    };
    void poll();
    return () => {
      cancelled = true;
      if (timeout) window.clearTimeout(timeout);
    };
  }, [jobId]);

  const startRender = async () => {
    if (!projectId) return;
    setCreatingJob(true);
    setError(null);
    try {
      const result = await createExportJob(projectId, config);
      setJobId(result.job_id);
      setStatus(result.status);
      setProgress(0);
      setArtifacts([]);
      setSourceFramesVersion(frames.artifact_version);
    } catch (createError) {
      setStatus("failed");
      setError(createError instanceof Error ? createError.message : "无法创建渲染任务");
    } finally {
      setCreatingJob(false);
    }
  };

  const stale = Boolean(
    sourceFramesVersion &&
    frames.artifact_version &&
    sourceFramesVersion !== frames.artifact_version,
  );
  const mp4 = artifacts.find((artifact) => artifact.type === "mp4");
  const totalSeconds = Math.round(
    frames.frames.reduce((sum, frame) => sum + (frame.duration_ms ?? 5000), 0) / 1000,
  );
  const selectedFrame = frames.frames[selectedFrameIndex] ?? frames.frames[0];
  const renderActive = status === "queued" || status === "rendering";
  const renderStage = status === "queued"
    ? 0
    : status === "rendering"
      ? Math.min(2, Math.max(1, Math.floor(progress / 40) + 1))
      : status === "completed" ? 3 : -1;
  const friendlyError = error ? toUserFacingError(error) : null;

  useEffect(() => {
    setSelectedFrameIndex((current) => Math.min(current, Math.max(frames.frames.length - 1, 0)));
  }, [frames.frames.length]);

  useEffect(() => {
    if (!targetFrameId) return;
    const targetIndex = frames.frames.findIndex((frame) => frame.frame_id === targetFrameId);
    if (targetIndex >= 0) setSelectedFrameIndex(targetIndex);
  }, [frames.frames, targetFrameId]);

  return (
    <div className="grid gap-4 p-4 xl:grid-cols-[minmax(0,1fr)_20rem]">
      <div className="min-w-0 space-y-4">
        <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="flex items-center gap-2 text-sm font-bold"><Film size={16} />视频分镜</h3>
              <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                {frames.frames.length} 个镜头 · 预计 {totalSeconds || 0} 秒 · 已结合讲解内容与画面脚本
              </p>
            </div>
            {stale ? (
              <Badge variant="destructive"><AlertTriangle />分镜已更新</Badge>
            ) : (
              <Badge variant="outline"><CheckCircle2 />版本一致</Badge>
            )}
          </div>
          {frames.frames.length > 0 ? (
            <div className="space-y-4">
              <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--code-bg)] shadow-sm">
                <div className="flex items-center justify-between gap-3 border-b border-white/10 px-3 py-2 text-white/75">
                  <div className="min-w-0">
                    <p className="font-mono text-[10px] text-white/45">
                      镜头 {String(selectedFrameIndex + 1).padStart(2, "0")} / {String(frames.frames.length).padStart(2, "0")}
                    </p>
                    <p className="truncate text-xs font-semibold">{selectedFrame?.title}</p>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="icon-xs"
                      aria-label="上一个镜头"
                      disabled={selectedFrameIndex === 0}
                      onClick={() => setSelectedFrameIndex((current) => Math.max(0, current - 1))}
                      className="text-white/70 hover:bg-white/10 hover:text-white"
                    >
                      <ChevronLeft />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon-xs"
                      aria-label="下一个镜头"
                      disabled={selectedFrameIndex >= frames.frames.length - 1}
                      onClick={() => setSelectedFrameIndex((current) => Math.min(frames.frames.length - 1, current + 1))}
                      className="text-white/70 hover:bg-white/10 hover:text-white"
                    >
                      <ChevronRight />
                    </Button>
                  </div>
                </div>
                <div className="video-storyboard-preview aspect-video overflow-auto bg-[var(--stage-bg)] p-4 sm:p-6">
                  <div className="grid h-full min-h-52 grid-cols-1 content-center gap-3 sm:grid-cols-2">
                    {selectedFrame?.visual_objects.slice(0, 4).map((object) => {
                      const isStructure = object.type === "graph" || object.type === "tree";
                      return (
                        <div
                          key={object.id}
                          className={cn(
                            "min-w-0 rounded-lg border border-[var(--border)] bg-[var(--card)]/95 p-3 shadow-sm",
                            isStructure && "min-h-44 sm:col-span-2",
                          )}
                        >
                          {object.label && <p className="mb-2 truncate text-[10px] font-semibold text-[var(--muted-foreground)]">{String(object.label)}</p>}
                          <VisualObjectRenderer object={object} className={isStructure ? "h-40 w-full" : undefined} />
                        </div>
                      );
                    })}
                    {selectedFrame?.visual_objects.length === 0 && (
                      <div className="flex h-full min-h-40 items-center justify-center text-center text-xs text-[var(--muted-foreground)] sm:col-span-2">
                        该镜头暂无可视对象，成片将以旁白和状态变化为主。
                      </div>
                    )}
                  </div>
                </div>
                <div className="border-t border-white/10 px-4 py-3 text-white/75">
                  <p className="line-clamp-2 text-xs leading-5">{selectedFrame?.narration || "该镜头暂无旁白"}</p>
                </div>
              </div>

              <div
                className="flex gap-2 overflow-x-auto pb-2"
                aria-label="视频分镜轨道"
                onWheel={(event) => {
                  if (Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return;
                  event.currentTarget.scrollLeft += event.deltaY;
                }}
              >
                {frames.frames.map((frame, index) => (
                  <button
                    key={frame.frame_id}
                    type="button"
                    aria-label={`选择镜头 ${index + 1}：${frame.title}`}
                    aria-pressed={selectedFrameIndex === index}
                    onClick={() => setSelectedFrameIndex(index)}
                    className={cn(
                      "group min-w-44 max-w-52 flex-1 rounded-lg border p-3 text-left outline-none transition-[border-color,box-shadow,transform] hover:-translate-y-0.5 focus-visible:ring-2 focus-visible:ring-[var(--interactive)]",
                      selectedFrameIndex === index
                        ? "border-[var(--interactive)] bg-[color-mix(in_oklch,var(--interactive)_9%,var(--card))] shadow-sm"
                        : "border-[var(--border)] bg-[var(--secondary)]/35 hover:border-[color-mix(in_oklch,var(--interactive)_45%,var(--border))]",
                    )}
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="font-mono text-[10px] text-[var(--muted-foreground)]">镜头 {String(index + 1).padStart(2, "0")}</span>
                      <span className="flex items-center gap-1 text-[10px] text-[var(--muted-foreground)]"><Clock3 size={11} />{Math.round((frame.duration_ms ?? 5000) / 1000)}s</span>
                    </span>
                    <span className="mt-2 block truncate text-xs font-semibold">{frame.title}</span>
                    <span className="mt-1 line-clamp-2 text-[10px] leading-4 text-[var(--muted-foreground)]">{frame.narration || "暂无旁白"}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <p className="rounded-lg border border-dashed p-8 text-center text-sm text-[var(--muted-foreground)]">
              暂无视频分镜，重新生成教学视频后会自动补充讲解画面。
            </p>
          )}
        </section>

        {status === "completed" && mp4 && (
          <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
            <h3 className="mb-3 text-sm font-bold">成片预览</h3>
            <video controls className="w-full rounded-lg bg-black" src={mp4.url}>您的浏览器不支持视频播放</video>
          </section>
        )}
      </div>

      <aside className="space-y-4 xl:sticky xl:top-4 xl:self-start">
        <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
          <p className="text-xs font-semibold text-[var(--muted-foreground)]">视频制作状态</p>
          <div className="mt-3 flex items-center gap-2">
            {(status === "queued" || status === "rendering") && <LoaderCircle className="animate-spin text-[var(--interactive)]" size={18} />}
            {status === "completed" && <CheckCircle2 className="text-[var(--success)]" size={18} />}
            {status === "failed" && <AlertTriangle className="text-[var(--error)]" size={18} />}
            <span className="text-sm font-semibold">
              {status === "queued" ? "等待制作" : status === "rendering" ? "正在制作" : status === "completed" ? "视频已完成" : status === "failed" ? "视频制作未完成" : "尚未开始制作"}
            </span>
          </div>
          {renderActive && (
            <div className="mt-3 space-y-2">
              <Progress className="h-1.5" value={progress} aria-label="视频渲染进度" />
              <div className="grid grid-cols-4 gap-1" aria-label="渲染阶段">
                {["准备", "画面", "合成", "完成"].map((label, index) => (
                  <span
                    key={label}
                    className={cn(
                      "rounded px-1 py-1 text-center text-[9px]",
                      index <= renderStage
                        ? "bg-[var(--interactive)] text-[var(--card)]"
                        : "bg-[var(--secondary)] text-[var(--muted-foreground)]",
                    )}
                  >
                    {label}
                  </span>
                ))}
              </div>
              <p className="text-right font-mono text-[10px] tabular-nums text-[var(--muted-foreground)]">{Math.round(progress)}%</p>
            </div>
          )}
          {friendlyError && (
            <div className="mt-3 rounded-md bg-[color-mix(in_oklch,var(--error)_7%,var(--card))] p-3">
              <p className="text-xs font-semibold text-[var(--error)]">{friendlyError.title}</p>
              <p className="mt-1 text-xs leading-5 text-[var(--muted-foreground)]">{friendlyError.message} {friendlyError.suggestion}</p>
            </div>
          )}
          {!jobId && <p className="mt-3 text-xs leading-5 text-[var(--muted-foreground)]">配置输出选项后即可创建新的渲染任务。</p>}
          {stale && <p className="mt-3 text-xs leading-5 text-[var(--error)]">讲解分镜已有更新，建议重新制作视频后再导出。</p>}
        </section>

        <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
          <p className="mb-3 text-xs font-semibold text-[var(--muted-foreground)]">输出设置</p>
          <div className="space-y-4 text-xs">
            <fieldset>
              <legend className="mb-2 text-[var(--muted-foreground)]">画质</legend>
              <div className="grid grid-cols-2 gap-1.5">
                {qualityOptions.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    aria-label={`视频画质 ${option.label}`}
                    aria-pressed={config.quality === option.value}
                    onClick={() => setConfig((current) => ({ ...current, quality: option.value }))}
                    className={cn(
                      "rounded-md border px-2 py-2 text-left outline-none transition-colors focus-visible:ring-2 focus-visible:ring-[var(--interactive)]",
                      config.quality === option.value
                        ? "border-[var(--interactive)] bg-[color-mix(in_oklch,var(--interactive)_10%,var(--card))]"
                        : "border-[var(--border)] hover:bg-[var(--secondary)]",
                    )}
                  >
                    <span className="block font-mono font-semibold">{option.label}</span>
                    <span className="mt-0.5 block text-[9px] text-[var(--muted-foreground)]">{option.note}</span>
                  </button>
                ))}
              </div>
            </fieldset>
            <fieldset>
              <legend className="mb-2 text-[var(--muted-foreground)]">帧率</legend>
              <div className="grid grid-cols-3 gap-1.5">
                {fpsOptions.map((fps) => (
                  <button
                    key={fps}
                    type="button"
                    aria-label={`视频帧率 ${fps} fps`}
                    aria-pressed={config.fps === fps}
                    onClick={() => setConfig((current) => ({ ...current, fps }))}
                    className={cn(
                      "rounded-md border px-2 py-2 font-mono outline-none transition-colors focus-visible:ring-2 focus-visible:ring-[var(--interactive)]",
                      config.fps === fps
                        ? "border-[var(--interactive)] bg-[color-mix(in_oklch,var(--interactive)_10%,var(--card))] font-semibold"
                        : "border-[var(--border)] hover:bg-[var(--secondary)]",
                    )}
                  >
                    {fps}
                  </button>
                ))}
              </div>
            </fieldset>
            <label className="flex cursor-pointer items-center justify-between gap-2 rounded-md border border-[var(--border)] px-3 py-2.5 transition-colors hover:bg-[var(--secondary)]">
              <span className="flex items-center gap-2"><Captions size={14} />包含字幕</span>
              <input
                aria-label="包含字幕"
                type="checkbox"
                checked={config.include_subtitles}
                onChange={(event) => setConfig((current) => ({ ...current, include_subtitles: event.target.checked }))}
                className="accent-[var(--interactive)]"
              />
            </label>
            <label className="flex cursor-pointer items-center justify-between gap-2 rounded-md border border-[var(--border)] px-3 py-2.5 transition-colors hover:bg-[var(--secondary)]">
              <span className="flex items-center gap-2"><Mic2 size={14} />包含语音</span>
              <input
                aria-label="包含语音"
                type="checkbox"
                checked={config.include_tts}
                onChange={(event) => setConfig((current) => ({ ...current, include_tts: event.target.checked }))}
                className="accent-[var(--interactive)]"
              />
            </label>
            <Button
              className="w-full"
              disabled={!projectId || creatingJob || Boolean(jobId && (status === "rendering" || status === "queued"))}
              onClick={startRender}
            >
              {creatingJob && <LoaderCircle className="animate-spin" />}
              {!creatingJob && <MonitorPlay />}
              {jobId ? "按当前设置重新渲染" : "开始渲染"}
            </Button>
          </div>
        </section>

        {artifacts.length > 0 && (
          <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
            <p className="mb-2 text-xs font-semibold text-[var(--muted-foreground)]">导出文件</p>
            <div className="space-y-1">
              {artifacts.map((artifact) => (
                <a key={artifact.type} href={artifact.url} download className="flex items-center justify-between rounded-md px-2 py-2 text-xs text-[var(--interactive)] hover:bg-[var(--secondary)]">
                  <span>
                    <span className="block">{artifact.type === "mp4" ? "教学视频" : artifact.type === "manim_source" ? "Manim 源码" : "字幕文件"}</span>
                    {artifact.size_bytes > 0 && <span className="mt-0.5 block font-mono text-[9px] text-[var(--muted-foreground)]">{formatFileSize(artifact.size_bytes)}</span>}
                  </span>
                  <Download size={14} />
                </a>
              ))}
            </div>
          </section>
        )}
      </aside>
    </div>
  );
}
