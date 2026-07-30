/**
 * 统一项目工作区 — 聚合计划/推演/编辑/导出四个 Tab。
 *
 * GET /app/project/:id?tab=plan|play|edit|export
 * 无 ?tab 时根据项目 status 自动选择默认 Tab。
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useSearchParams, Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import {
  ArrowLeft,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Sparkles,
  RefreshCw,
  Play,
  Pause,
  SkipBack,
  SkipForward,
  RotateCcw,
  Pencil,
  Save,
  Lock,
  Unlock,
  History,
  Film,
  Download,
  FileText,
} from "lucide-react";
import {
  getProject,
  startGeneration,
  streamGeneration,
  streamFromUrl,
  approvePlan,
  rejectPlan,
  listFrames,
  updateFrame,
  lockFrame,
  regenerate,
  saveVersion,
  listVersions,
  restoreVersion,
  createExportJob,
  getExportStatus,
  listModules,
  startModuleGeneration,
  streamModuleGeneration,
  type ProjectDetailResponse,
  type FrameData,
  type SSEProgressEvent,
  type SSEWaitingApprovalEvent,
  type SSEModuleStartEvent,
  type SSEModuleDoneEvent,
  type SSEModuleErrorEvent,
  type ExportJobResponse,
  type VersionItem,
  type ModuleInfo,
  NetworkError,
} from "@/services";
import { VisualObjectRenderer } from "@/components/workbench/visual-objects/VisualObjectRenderer";
import type { DSLVisualObject } from "@/components/workbench/simulation-model";
import { ModuleSelector } from "@/features/modules/ModuleSelector";
import { ModuleProgress, type ModuleProgressItem } from "@/features/modules/ModuleProgress";
import { ModuleResultsPanel } from "@/features/modules/ModuleResultsPanel";

// ============================================================================
// Tab 类型
// ============================================================================

type ProjectTab = "plan" | "play" | "edit" | "results" | "export";

const TABS: { key: ProjectTab; label: string; icon: typeof Sparkles }[] = [
  { key: "plan", label: "计划", icon: Sparkles },
  { key: "play", label: "推演", icon: Play },
  { key: "edit", label: "编辑", icon: Pencil },
  { key: "results", label: "成果", icon: FileText },
  { key: "export", label: "导出", icon: Film },
];

const STATUS_DEFAULT_TAB: Record<string, ProjectTab> = {
  draft: "plan",
  planning: "plan",
  generating: "plan",
  reviewing: "play",
  done: "results",
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isVisualObject(value: unknown): value is DSLVisualObject {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.type === "string"
  );
}

function getString(value: unknown, fallback: string) {
  return typeof value === "string" ? value : fallback;
}

// ============================================================================
// 容器
// ============================================================================

export function ProjectWorkspace() {
  const { projectId } = useParams<{ projectId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();

  const tabFromUrl = (searchParams.get("tab") ?? "") as ProjectTab;
  const [project, setProject] = useState<ProjectDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);

  // 加载项目
  useEffect(() => {
    if (!projectId) return;
    setLoading(true);
    getProject(projectId)
      .then(setProject)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [projectId]);

  // 确定当前 Tab
  const activeTab: ProjectTab = (() => {
    if (TABS.some((t) => t.key === tabFromUrl)) return tabFromUrl;
    if (project?.status === "done" && !project?.module_outputs) return "play";
    if (project?.status) return STATUS_DEFAULT_TAB[project.status] ?? "plan";
    return "plan";
  })();

  const setTab = (tab: ProjectTab) => {
    setSearchParams({ tab });
  };

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <div className="w-full max-w-2xl space-y-4">
          <Skeleton className="h-8 w-1/3" />
          <Skeleton className="h-6 w-full" />
          <Skeleton className="h-64 w-full rounded-xl" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* 顶部栏 */}
      <header className="flex shrink-0 items-center justify-between gap-3 border-b px-4 py-2.5">
        <div className="flex min-w-0 items-center gap-3">
          <Link to="/app" className="text-muted-foreground hover:text-foreground shrink-0">
            <ArrowLeft size={17} />
          </Link>
          <h1 className="text-sm font-semibold truncate">
            {project?.title ?? "项目"}
          </h1>
          {project?.status && (
            <Badge variant="outline" className="shrink-0 text-[10px]">
              {project.status === "done" ? "已完成" :
               project.status === "draft" ? "草稿" :
               project.status === "planning" ? "规划中" :
               project.status === "generating" ? "生成中" :
               project.status === "reviewing" ? "校验中" : project.status}
            </Badge>
          )}
        </div>

        {/* 右侧快速操作 */}
        <div className="flex items-center gap-1.5 shrink-0">
          {activeTab !== "edit" && (
            <Button variant="ghost" size="sm" className="gap-1 text-xs" onClick={() => setTab("edit")}>
              <Pencil size={14} /> 编辑
            </Button>
          )}
          {activeTab !== "export" && (
            <Button variant="ghost" size="sm" className="gap-1 text-xs" onClick={() => setTab("export")}>
              <Download size={14} /> 导出
            </Button>
          )}
        </div>
      </header>

      {/* Tab 导航 */}
      <nav className="flex shrink-0 items-center gap-0 border-b px-4" aria-label="项目导航">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`flex items-center gap-1.5 px-3 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-[1px] ${
              activeTab === key
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <Icon size={14} />
            {label}
          </button>
        ))}
      </nav>

      {/* 内容区 */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        {activeTab === "plan" && projectId && (
          <PlanTabContent projectId={projectId} project={project} onDone={() => setTab("play")} />
        )}
        {activeTab === "play" && projectId && (
          <PlayTabContent projectId={projectId} project={project} />
        )}
        {activeTab === "edit" && projectId && (
          <EditTabContent projectId={projectId} />
        )}
        {activeTab === "results" && projectId && (
          <ModuleResultsPanel
            project={project}
            onNavigateTab={(tab) => setTab(tab as ProjectTab)}
          />
        )}
        {activeTab === "export" && projectId && (
          <ExportTabContent projectId={projectId} />
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Tab: 计划（原 PlanConfirm）
// ============================================================================

type SSEPhase = "idle" | "connecting" | "planning" | "waiting_approval" | "module_selection" | "module_generating" | "generating" | "validating" | "done" | "error";

function PlanTabContent({ projectId, project, onDone }: {
  projectId: string;
  project: ProjectDetailResponse | null;
  onDone: () => void;
}) {
  const [phase, setPhase] = useState<SSEPhase>("idle");
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState("");
  const [teachingPlan, setTeachingPlan] = useState<Record<string, unknown> | null>(null);
  const [qualityReport, setQualityReport] = useState<Record<string, unknown> | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const startedRef = useRef(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>();

  // 模块选择状态（Phase A）
  const [availableModules, setAvailableModules] = useState<ModuleInfo[]>([]);
  const [moduleStatuses, setModuleStatuses] = useState<Map<string, ModuleProgressItem>>(new Map());
  const [moduleOutputs, setModuleOutputs] = useState<Record<string, unknown>>({});

  // 连接超时检测：LLM 调用可能较慢，60 秒内无进展 → 报错
  const resetTimeout = useCallback(() => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => {
      setPhase((prev) => {
        if (prev === "connecting" || prev === "planning" || prev === "generating") {
          setErrorMsg("连接超时，请确认后端服务已启动（http://localhost:8000）");
          return "error";
        }
        return prev;
      });
    }, 60000);
  }, []);

  useEffect(() => {
    return () => { if (timeoutRef.current) clearTimeout(timeoutRef.current); };
  }, []);

  const handleStart = useCallback(async () => {
    if (startedRef.current) return;
    startedRef.current = true;
    setPhase("connecting");
    setErrorMsg(null);
    resetTimeout();

    try {
      await startGeneration(projectId, "plan_only");
      abortRef.current?.abort();
      abortRef.current = new AbortController();

      streamGeneration(projectId, {
        signal: abortRef.current.signal,
        onProgress: (event: SSEProgressEvent) => {
          if (timeoutRef.current) clearTimeout(timeoutRef.current);
          setProgress(event.pct);
          setMessage(event.message);
          if (event.phase === "planning") {
            setPhase("planning");
            if (event.teaching_plan) setTeachingPlan(event.teaching_plan as Record<string, unknown>);
          } else if (event.phase === "generating" || event.phase === "knowledge" || event.phase === "coder") {
            setPhase("generating");
          } else if (event.phase === "validating" || event.phase === "quality") {
            setPhase("validating");
          }
        },
        onWaitingApproval: (event: SSEWaitingApprovalEvent) => {
          if (timeoutRef.current) clearTimeout(timeoutRef.current);
          setPhase("waiting_approval");
          setProgress(event.pct);
          setMessage(event.message);
          if (event.teaching_plan) setTeachingPlan(event.teaching_plan as Record<string, unknown>);
        },
        onDone: (event) => {
          setPhase("done");
          setProgress(100);
          setMessage("生成完成");
          if (event.quality_report) setQualityReport(event.quality_report as Record<string, unknown>);
          onDone();
        },
        onError: (event) => {
          setPhase("error");
          setErrorMsg(event.message || "生成过程中发生错误");
        },
      });
    } catch (err) {
      setPhase("error");
      if (err instanceof NetworkError) setErrorMsg("无法连接到服务器");
      else setErrorMsg(err instanceof Error ? err.message : "生成启动失败");
    }
  }, [projectId, onDone]);

  useEffect(() => {
    return () => { abortRef.current?.abort(); };
  }, []);

  // ── 审批操作 ─────────────────────────────────────────────────
  const handleApprove = useCallback(async () => {
    if (!projectId) return;
    try {
      const res = await approvePlan(projectId);
      // Phase A: 如果后端返回了 available_modules（新模块选择流程）
      if (res.available_modules && res.available_modules.length > 0) {
        setAvailableModules(res.available_modules);
        setPhase("module_selection");
        setProgress(30);
        setMessage("请选择要生成的模块");
        return;
      }
      // 旧流程: 连接 resume 流从中断点继续
      setPhase("connecting");
      setErrorMsg(null);
      resetTimeout();
      abortRef.current?.abort();
      abortRef.current = new AbortController();
      streamFromUrl(res.stream_url, {
        signal: abortRef.current.signal,
        onProgress: (event: SSEProgressEvent) => {
          if (timeoutRef.current) clearTimeout(timeoutRef.current);
          setProgress(event.pct);
          setMessage(event.message);
          if (event.phase === "generating" || event.phase === "knowledge" || event.phase === "coder") {
            setPhase("generating");
          } else if (event.phase === "validating" || event.phase === "quality") {
            setPhase("validating");
          }
        },
        onDone: (event) => {
          setPhase("done");
          setProgress(100);
          setMessage("生成完成");
          if (event.quality_report) setQualityReport(event.quality_report as Record<string, unknown>);
          onDone();
        },
        onError: (event) => {
          setPhase("error");
          setErrorMsg(event.message || "生成过程中发生错误");
        },
      });
    } catch (err) {
      setPhase("error");
      if (err instanceof NetworkError) setErrorMsg("无法连接到服务器");
      else setErrorMsg(err instanceof Error ? err.message : "批准失败");
    }
  }, [projectId, onDone, resetTimeout]);

  // ── 模块选择 ─────────────────────────────────────────────────
  const handleStartModules = useCallback(async (selectedIds: string[]) => {
    if (!projectId || selectedIds.length === 0) return;
    try {
      await startModuleGeneration(projectId, selectedIds);
      setPhase("module_generating");
      setErrorMsg(null);
      const statuses = new Map<string, ModuleProgressItem>();
      for (const id of selectedIds) {
        const mod = availableModules.find((m) => m.module_id === id);
        statuses.set(id, { module_id: id, display_name: mod?.display_name ?? id, status: "pending" });
      }
      setModuleStatuses(new Map(statuses));
      abortRef.current?.abort();
      abortRef.current = new AbortController();
      streamModuleGeneration(projectId, {
        signal: abortRef.current.signal,
        onModuleStart: (event: SSEModuleStartEvent) => {
          setModuleStatuses((prev) => {
            const next = new Map(prev);
            const existing = next.get(event.module_id);
            if (existing) next.set(event.module_id, { ...existing, status: "running" });
            return next;
          });
          setMessage(event.message);
          setProgress(event.pct);
        },
        onModuleDone: (event: SSEModuleDoneEvent) => {
          setModuleStatuses((prev) => {
            const next = new Map(prev);
            const existing = next.get(event.module_id);
            if (existing) next.set(event.module_id, { ...existing, status: "done" });
            return next;
          });
          setModuleOutputs((prev) => ({ ...prev, [event.module_id]: event.output }));
          setProgress(event.pct);
        },
        onModuleError: (event: SSEModuleErrorEvent) => {
          setModuleStatuses((prev) => {
            const next = new Map(prev);
            const existing = next.get(event.module_id);
            if (existing) next.set(event.module_id, { ...existing, status: "error", error: event.error });
            return next;
          });
          setProgress(event.pct);
        },
        onDone: (event) => {
          setPhase("done");
          setProgress(100);
          setMessage("模块生成完成");
          if (event.module_outputs) setModuleOutputs(event.module_outputs as Record<string, unknown>);
          onDone();
        },
        onError: (event) => {
          setPhase("error");
          setErrorMsg(event.message || "模块生成失败");
        },
      });
    } catch (err) {
      setPhase("error");
      if (err instanceof NetworkError) setErrorMsg("无法连接到服务器");
      else setErrorMsg(err instanceof Error ? err.message : "模块生成启动失败");
    }
  }, [projectId, availableModules, onDone]);

  const handleReject = useCallback(async (feedback: string) => {
    if (!projectId) return;
    try {
      // 注入拒绝决定让图消费中断点（结果通过 resume 流结束），随后回到 idle
      const res = await rejectPlan(projectId, feedback);
      streamFromUrl(res.stream_url, {
        onDone: () => {},
        onError: () => {},
      });
      setPhase("idle");
      startedRef.current = false;
      setMessage("已返回修改，请调整主题描述后重新生成");
    } catch (err) {
      if (err instanceof NetworkError) setErrorMsg("无法连接到服务器");
      else setErrorMsg(err instanceof Error ? err.message : "提交失败");
    }
  }, [projectId]);

  return (
    <div className="mx-auto max-w-3xl p-6">
      <h2 className="text-lg font-bold mb-1">教学计划</h2>
      <p className="text-sm text-muted-foreground mb-6">{project?.title}</p>

      {phase === "idle" && (
        <div className="rounded-xl border p-8 text-center">
          <Sparkles size={48} className="mx-auto mb-4 text-primary" />
          <h3 className="font-semibold mb-2">准备生成教学计划</h3>
          <p className="text-sm text-muted-foreground mb-6">AI 将分析知识点，制定教学目标、大纲和推演策略</p>
          <Button onClick={handleStart} className="gap-2">
            <Sparkles size={18} /> 开始生成
          </Button>
        </div>
      )}

      {(phase === "connecting" || phase === "planning" || phase === "generating" || phase === "validating") && (
        <div className="space-y-6">
          <div className="rounded-xl border p-6">
            <div className="flex items-center gap-3 mb-4">
              <Sparkles size={20} className="text-primary animate-pulse" />
              <div>
                <p className="font-medium">
                  {phase === "connecting" && "正在连接..."}
                  {phase === "planning" && "正在制定教学计划"}
                  {phase === "generating" && "正在生成推演帧"}
                  {phase === "validating" && "正在校验质量"}
                </p>
                <p className="text-sm text-muted-foreground">{message}</p>
              </div>
            </div>
            <Progress value={progress} className="h-2" />
            <p className="mt-2 text-right text-xs text-muted-foreground">{progress}%</p>
          </div>

          {teachingPlan && (
            <div className="rounded-xl border p-6">
              <h3 className="font-semibold mb-4">教学计划</h3>
              <pre className="max-h-64 overflow-auto rounded-lg bg-muted p-4 text-xs">
                {JSON.stringify(teachingPlan, null, 2)}
              </pre>
            </div>
          )}

          <div className="text-center">
            <Button variant="outline" size="sm" onClick={() => {
              abortRef.current?.abort();
              setPhase("idle");
              startedRef.current = false;
            }} className="gap-2">
              <XCircle size={16} /> 取消
            </Button>
          </div>
        </div>
      )}

      {phase === "waiting_approval" && teachingPlan && (
        <div className="space-y-6">
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-6">
            <div className="flex items-start gap-3">
              <AlertTriangle size={20} className="text-amber-500 mt-0.5 shrink-0" />
              <div>
                <h3 className="font-semibold text-amber-800 mb-1">确认教学计划</h3>
                <p className="text-sm text-amber-600">AI 已生成教学计划，请审核后决定是否继续</p>
              </div>
            </div>
          </div>

          <div className="rounded-xl border p-6">
            <h3 className="font-semibold mb-4">教学计划预览</h3>
            <pre className="max-h-96 overflow-auto rounded-lg bg-muted p-4 text-xs">
              {JSON.stringify(teachingPlan, null, 2)}
            </pre>
          </div>

          <div className="flex gap-3 justify-center">
            <Button
              onClick={handleApprove}
              className="gap-2"
            >
              <CheckCircle2 size={16} /> 批准，继续生成
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                const feedback = prompt("请输入修改意见（可选）：") || "";
                handleReject(feedback);
              }}
              className="gap-2"
            >
              <RefreshCw size={16} /> 需要修改
            </Button>
          </div>
        </div>
      )}

      {phase === "module_selection" && (
        <div className="space-y-6">
          <div className="rounded-xl border border-blue-200 bg-blue-50 p-6">
            <div className="flex items-start gap-3">
              <Sparkles size={20} className="text-blue-500 mt-0.5 shrink-0" />
              <div>
                <h3 className="font-semibold text-blue-800 mb-1">教学计划已批准</h3>
                <p className="text-sm text-blue-600">请选择需要生成的产出形式</p>
              </div>
            </div>
          </div>
          <ModuleSelector
            modules={availableModules}
            onStart={handleStartModules}
          />
        </div>
      )}

      {phase === "module_generating" && (
        <div className="space-y-6">
          <div className="rounded-xl border p-6">
            <div className="flex items-center gap-3 mb-4">
              <Sparkles size={20} className="text-primary animate-pulse" />
              <div>
                <p className="font-medium">正在生成模块...</p>
                <p className="text-sm text-muted-foreground">{message}</p>
              </div>
            </div>
            <Progress value={progress} className="mb-4" />
            <ModuleProgress
              modules={[...moduleStatuses.values()]}
              totalPct={progress}
            />
          </div>
        </div>
      )}

      {phase === "done" && (
        <div className="space-y-6">
          <div className="rounded-xl border border-green-200 bg-green-50 p-6 text-center">
            <CheckCircle2 size={48} className="mx-auto mb-4 text-green-500" />
            <h3 className="font-semibold text-green-800 mb-2">生成完成</h3>
            <p className="text-sm text-green-600">教学计划和推演帧已生成完毕</p>
          </div>
          {qualityReport && (
            <div className="rounded-xl border p-6">
              <h3 className="font-semibold mb-4">质量报告</h3>
              <pre className="max-h-64 overflow-auto rounded-lg bg-muted p-4 text-xs">
                {JSON.stringify(qualityReport, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}

      {phase === "error" && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center">
          <AlertTriangle size={48} className="mx-auto mb-4 text-red-400" />
          <h3 className="font-semibold text-red-800 mb-2">生成失败</h3>
          <p className="text-sm text-red-600 mb-6">{errorMsg}</p>
          <Button variant="outline" onClick={() => { setPhase("idle"); startedRef.current = false; }} className="gap-2">
            <RefreshCw size={16} /> 重试
          </Button>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Tab: 推演 — 可视化舞台 + 播放控制
// ============================================================================

const PLAY_SPEEDS = [
  { label: "0.5×", ms: 3000 },
  { label: "1×", ms: 2000 },
  { label: "2×", ms: 1000 },
  { label: "4×", ms: 500 },
];

type PlayState = "idle" | "playing" | "paused";

function usePlayback(onFrame: (i: number) => void) {
  const [state, setState] = useState<PlayState>("idle");
  const [speedIdx, setSpeedIdx] = useState(1);
  const timerRef = useRef<ReturnType<typeof setInterval>>();

  const stop = useCallback(() => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = undefined; }
    setState("idle");
  }, []);

  const play = useCallback(() => {
    setState("playing");
  }, []);

  const pause = useCallback(() => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = undefined; }
    setState("paused");
  }, []);

  const toggle = useCallback(() => {
    if (state === "playing") pause(); else play();
  }, [state, play, pause]);

  // auto-advance
  useEffect(() => {
    if (state !== "playing") return;
    timerRef.current = setInterval(() => {
      onFrame(-1); // sentinel: advance by 1 (handled in caller)
    }, PLAY_SPEEDS[speedIdx]?.ms ?? 2000);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [state, speedIdx, onFrame]);

  return { state, speedIdx, setSpeedIdx, stop, play, pause, toggle };
}

/** 当 visual_objects 为空时，用 state_snapshot 渲染降级表格 */
function StateSnapshotFallback({ snapshot }: { snapshot: Record<string, unknown> }) {
  const entries = Object.entries(snapshot).filter(
    ([, v]) => v != null && v !== "" && !(Array.isArray(v) && v.length === 0),
  );
  if (entries.length === 0) return null;

  return (
    <div className="w-full max-w-lg rounded-lg border bg-card text-sm overflow-hidden">
      <div className="bg-muted/50 px-3 py-1.5 text-xs font-semibold text-muted-foreground">算法状态</div>
      <div className="divide-y">
        {entries.map(([key, value]) => (
          <div key={key} className="flex items-start gap-3 px-3 py-2">
            <span className="text-xs font-mono text-primary shrink-0 min-w-[80px] pt-0.5">{key}</span>
            <span className="text-xs text-muted-foreground break-all font-mono">
              {typeof value === "object" ? JSON.stringify(value) : String(value)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function PlayTabContent({ projectId, project }: {
  projectId: string;
  project: ProjectDetailResponse | null;
}) {
  const [frames, setFrames] = useState<FrameData[]>([]);
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [stageKey, setStageKey] = useState(0); // triggers enter animation on frame change

  useEffect(() => {
    if (!projectId) return;
    listFrames(projectId).then((fd) => setFrames(fd.frames ?? [])).catch(() => {});
  }, [projectId]);

  // 帧数据源：DSL snapshot 优先
  const dslFrames = Array.isArray(project?.dsl?.frames)
    ? project.dsl.frames.filter(isRecord)
    : [];
  const displayFrames = dslFrames.length > 0 ? dslFrames : frames;

  const advance = useCallback((target: number) => {
    setSelectedIdx((prev) => {
      const next = target === -1 ? prev + 1 : target;
      return Math.max(0, Math.min(displayFrames.length - 1, next));
    });
    setStageKey((k) => k + 1);
  }, [displayFrames.length]);

  const playback = usePlayback(advance);

  // 播到末尾自动停
  useEffect(() => {
    if (selectedIdx >= displayFrames.length - 1 && playback.state === "playing") {
      playback.stop();
    }
  }, [selectedIdx, displayFrames.length, playback]);

  // 键盘快捷键（使用 ref 避免每帧重新注册监听器）
  const playbackRef = useRef(playback);
  playbackRef.current = playback;
  const advanceRef = useRef(advance);
  advanceRef.current = advance;
  const selectedIdxRef = useRef(selectedIdx);
  selectedIdxRef.current = selectedIdx;
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.key === " ") { e.preventDefault(); playbackRef.current.toggle(); }
      if (e.key === "ArrowLeft") { e.preventDefault(); advanceRef.current(selectedIdxRef.current - 1); }
      if (e.key === "ArrowRight") { e.preventDefault(); advanceRef.current(selectedIdxRef.current + 1); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const currentFrame = displayFrames[selectedIdx] as Record<string, unknown> | undefined;
  const currentFrameId = getString(currentFrame?.frame_id, `f_${selectedIdx + 1}`);
  const currentFrameTitle = getString(currentFrame?.title, "未命名帧");
  const currentFrameNarration = getString(currentFrame?.narration, "");
  const visualObjects = Array.isArray(currentFrame?.visual_objects)
    ? currentFrame.visual_objects.filter(isVisualObject)
    : [];
  const stateSnapshot = isRecord(currentFrame?.state_snapshot)
    ? currentFrame.state_snapshot
    : null;
  const animations = Array.isArray(currentFrame?.animations)
    ? currentFrame.animations.filter(isRecord)
    : [];

  if (displayFrames.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-center">
        <FileText size={48} className="text-muted-foreground/30 mb-4" />
        <h3 className="font-semibold mb-1">尚未生成推演内容</h3>
        <p className="text-sm text-muted-foreground">前往"计划"Tab 启动生成流程</p>
      </div>
    );
  }

  return (
    <div className="flex flex-1 min-h-0 overflow-hidden">
      {/* 左侧帧列表 */}
      <aside className="w-52 shrink-0 border-r overflow-y-auto bg-muted/30 scrollbar-none">
        <div className="sticky top-0 z-10 bg-muted/30 border-b px-3 py-2 flex items-center justify-between">
          <span className="text-xs font-semibold text-muted-foreground">{displayFrames.length} 帧</span>
          {playback.state === "playing" && (
            <span className="size-1.5 rounded-full bg-green-500 animate-pulse" />
          )}
        </div>
        {displayFrames.map((frame: any, idx: number) => (
          <button
            key={frame.frame_id ?? idx}
            onClick={() => { playback.stop(); advance(idx); }}
            className={`w-full text-left px-3 py-2.5 text-sm transition-colors border-b border-border/30 ${
              selectedIdx === idx
                ? "bg-primary/10 text-primary font-medium border-l-2 border-l-primary"
                : "border-l-2 border-l-transparent hover:bg-muted"
            }`}
          >
            <span className="text-[10px] font-mono text-muted-foreground">{getString(frame.frame_id, `f_${idx + 1}`)}</span>
            <p className="text-xs font-medium truncate mt-0.5 leading-tight">{getString(frame.title, "未命名")}</p>
            {frame.narration && (
              <p className="text-[11px] text-muted-foreground truncate mt-0.5 leading-tight">
                {getString(frame.narration, "")}
              </p>
            )}
          </button>
        ))}
      </aside>

      {/* 右侧：舞台 + 讲解 + 控制 */}
      <main className="flex-1 flex flex-col min-h-0 min-w-0 overflow-hidden">
        <div className="flex-1 flex flex-col items-center justify-center p-6 overflow-hidden">
          {/* 舞台卡片 */}
          <div className="w-full max-w-3xl max-h-full rounded-xl border bg-card shadow-sm flex flex-col overflow-hidden">
            {/* 帧标题（固定不滚） */}
            <div className="shrink-0 flex items-center justify-between px-5 py-3 border-b bg-muted/30">
              <div>
                <span className="text-xs font-mono text-muted-foreground">{currentFrameId}</span>
                <h3 className="text-base font-bold mt-0.5">{currentFrameTitle}</h3>
              </div>
              <span className="text-xs font-mono text-muted-foreground">
                {selectedIdx + 1} / {displayFrames.length}
              </span>
            </div>

            {/* 卡片可滚动内容区 */}
            <div className="flex-1 overflow-y-auto">
              {/* 舞台区域 */}
              <div key={stageKey} className="relative simulation-stage min-h-[220px]">
                <div className="flex items-center justify-center p-8 min-h-[220px]">
                  {visualObjects.length > 0 ? (
                    <div className="flex flex-wrap items-center justify-center gap-5">
                      {visualObjects.map((vo) => (
                        <div key={vo.id} className="simulation-stage__object">
                          <VisualObjectRenderer object={vo} />
                        </div>
                      ))}
                    </div>
                  ) : stateSnapshot && Object.keys(stateSnapshot).length > 0 ? (
                    <StateSnapshotFallback snapshot={stateSnapshot} />
                  ) : (
                    <div className="text-center text-muted-foreground/30">
                      <FileText size={40} className="mx-auto mb-2 opacity-20" />
                      <p className="text-sm">待生成可视化内容</p>
                    </div>
                  )}
                </div>
              </div>

              {/* 讲解文本 */}
              {currentFrameNarration && (
                <div className="border-t bg-muted/30 px-5 py-3.5">
                  <div className="flex gap-2.5">
                    <Sparkles size={15} className="mt-0.5 shrink-0 text-primary" />
                    <p className="text-sm leading-relaxed text-muted-foreground">{currentFrameNarration}</p>
                  </div>
                </div>
              )}

              {/* 状态快照详情 */}
              {stateSnapshot && Object.keys(stateSnapshot).length > 0 && visualObjects.length === 0 && (
                <div className="border-t px-5 py-3.5">
                  <h4 className="text-xs font-semibold text-muted-foreground mb-2">状态快照</h4>
                  <pre className="max-h-48 overflow-auto rounded-lg bg-muted p-3 text-xs font-mono">
                    {JSON.stringify(stateSnapshot, null, 2)}
                  </pre>
                </div>
              )}

              {/* 动画列表 */}
              {animations.length > 0 && (
                <div className="border-t px-5 py-3.5">
                  <h4 className="text-xs font-semibold text-muted-foreground mb-2">
                    动画序列 ({animations.length})
                  </h4>
                  <div className="flex flex-wrap gap-1.5">
                    {animations.map((anim, idx) => (
                      <span key={idx} className="rounded-full bg-muted px-2.5 py-0.5 text-xs font-mono">
                        {getString(anim.type, "?")} → {getString(anim.target, "?")}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* 播放控制栏 */}
          <div className="mt-4 flex items-center gap-3 w-full max-w-3xl">
            <div className="flex items-center gap-1">
              <Button
                variant="outline" size="sm"
                disabled={selectedIdx <= 0}
                onClick={() => advance(selectedIdx - 1)}
              >
                <SkipBack size={15} /> 上一帧
              </Button>
              <Button
                size="sm"
                onClick={playback.toggle}
                className="gap-1.5 min-w-[5rem]"
              >
                {playback.state === "playing" ? (
                  <><Pause size={15} /> 暂停</>
                ) : (
                  <><Play size={15} /> 播放</>
                )}
              </Button>
              <Button
                variant="outline" size="sm"
                disabled={selectedIdx >= displayFrames.length - 1}
                onClick={() => advance(selectedIdx + 1)}
              >
                下一帧 <SkipForward size={15} />
              </Button>
            </div>

            <div className="flex-1 mx-2">
              <Progress value={((selectedIdx + 1) / displayFrames.length) * 100} className="h-1.5" />
            </div>

            <div className="flex items-center gap-0.5">
              {PLAY_SPEEDS.map((s, i) => (
                <Button
                  key={s.label}
                  variant={playback.speedIdx === i ? "default" : "ghost"}
                  size="sm"
                  className="h-7 px-2 text-xs"
                  onClick={() => playback.setSpeedIdx(i)}
                >
                  {s.label}
                </Button>
              ))}
            </div>

            <Button variant="ghost" size="sm" onClick={() => { playback.stop(); advance(0); }}>
              <RotateCcw size={14} />
            </Button>
          </div>
        </div>
      </main>
    </div>
  );
}


// ============================================================================
// Tab: 编辑（原 Editor）
// ============================================================================

function EditTabContent({ projectId }: { projectId: string }) {
  const [frames, setFrames] = useState<FrameData[]>([]);
  const [selected, setSelected] = useState<FrameData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");
  const [error, setError] = useState("");
  const [showVersions, setShowVersions] = useState(false);
  const [versions, setVersions] = useState<VersionItem[]>([]);
  // JSON 编辑 raw state（避免编辑中 JSON 不合法时输入被"吃掉"）
  const [visObjText, setVisObjText] = useState("");
  const [stateSnapText, setStateSnapText] = useState("");
  const [visObjError, setVisObjError] = useState("");
  const [stateSnapError, setStateSnapError] = useState("");

  // 切换帧时同步 raw text
  const syncRawTexts = (frame: FrameData) => {
    setVisObjText(JSON.stringify(frame.visual_objects, null, 2));
    setStateSnapText(JSON.stringify(frame.state_snapshot, null, 2));
    setVisObjError("");
    setStateSnapError("");
  };

  useEffect(() => {
    if (!projectId) return;
    setLoading(true);
    listFrames(projectId)
      .then((res) => {
        setFrames(res.frames);
        if (res.frames.length > 0) { setSelected(res.frames[0]); syncRawTexts(res.frames[0]); }
      })
      .catch((err) => {
        if (err instanceof NetworkError) setError("无法连接到服务器");
        else setError(err instanceof Error ? err.message : "加载失败");
      })
      .finally(() => setLoading(false));
  }, [projectId]);

  const fetchVersions = () => {
    if (!projectId) return;
    listVersions(projectId).then((res) => setVersions(res.versions)).catch(() => {});
  };

  useEffect(() => { fetchVersions(); }, [projectId]);

  const handleSave = async () => {
    if (!projectId || !selected) return;
    setSaving(true); setSaveMsg("");
    try {
      await updateFrame(projectId, selected.frame_id, {
        title: selected.title,
        narration: selected.narration,
        visual_objects: selected.visual_objects,
        state_snapshot: selected.state_snapshot,
        animations: selected.animations,
      });
      setSaveMsg("保存成功");
      setTimeout(() => setSaveMsg(""), 2000);
    } catch (err) {
      setSaveMsg(err instanceof Error ? err.message : "保存失败");
    } finally { setSaving(false); }
  };

  const handleLock = async (frameId: string, locked: boolean) => {
    if (!projectId) return;
    try {
      await lockFrame(projectId, frameId, locked);
      setFrames((prev) => prev.map((f) => f.frame_id === frameId ? { ...f, is_locked: locked } : f));
      if (selected?.frame_id === frameId) setSelected((prev) => prev ? { ...prev, is_locked: locked } : null);
    } catch { /* ignore */ }
  };

  const handleRegenerate = async () => {
    if (!projectId) return;
    try {
      const res = await regenerate(projectId, { type: "from_frame" });
      // 连接 regenerate SSE 流，done 时刷新帧列表
      streamFromUrl(res.stream_url, {
        onDone: async () => {
          try {
            const fd = await listFrames(projectId);
            setFrames(fd.frames);
            // 保持选中（如果 frame_id 仍存在）
            setSelected((prev) => {
              if (!prev) return null;
              const match = fd.frames.find((f) => f.frame_id === prev.frame_id);
              return match ?? fd.frames[0] ?? null;
            });
          } catch { /* ignore */ }
        },
        onError: () => { /* ignore */ },
      });
    } catch { /* ignore */ }
  };

  const handleSaveVersion = async () => {
    if (!projectId) return;
    try {
      await saveVersion(projectId, "手动保存");
      setSaveMsg("版本已保存");
      setTimeout(() => setSaveMsg(""), 2000);
      fetchVersions();
    } catch (err) {
      setSaveMsg(err instanceof Error ? err.message : "版本保存失败");
    }
  };

  if (loading) {
    return <div className="p-6 space-y-4"><Skeleton className="h-8 w-1/3" /><Skeleton className="h-64 w-full rounded-xl" /></div>;
  }

  if (error) {
    return <div className="flex flex-col items-center justify-center p-12"><AlertTriangle size={48} className="text-red-300 mb-4" /><p className="text-red-600">{error}</p></div>;
  }

  return (
    <div className="flex flex-1 min-h-0">
      {/* 左侧帧列表 */}
      <aside className="w-60 shrink-0 border-r overflow-y-auto bg-muted/30">
        <div className="p-3 flex items-center justify-between">
          <span className="text-xs font-semibold text-muted-foreground uppercase">{frames.length} 帧</span>
          <div className="flex gap-0.5">
            <Button variant="ghost" size="sm" className="h-6 px-1.5 text-[10px]" onClick={handleRegenerate}>
              <RefreshCw size={12} className="mr-1" />重生成
            </Button>
            <Button variant="ghost" size="sm" className="h-6 px-1.5 text-[10px]" onClick={() => setShowVersions(!showVersions)}>
              <History size={12} className="mr-1" />版本
            </Button>
          </div>
        </div>

        {showVersions && (
          <div className="border-t px-3 py-2">
            {versions.map((v) => (
              <div key={v.id} className="flex items-center justify-between text-xs py-1">
                <span>v{v.version} <span className="text-muted-foreground">{v.change_summary}</span></span>
                <Button variant="ghost" size="sm" className="h-5 px-1 text-[10px]" onClick={async () => {
                  if (!projectId) return;
                  await restoreVersion(projectId, v.id);
                  fetchVersions();
                  const res = await listFrames(projectId);
                  setFrames(res.frames);
                }}>恢复</Button>
              </div>
            ))}
          </div>
        )}

        {frames.map((f) => (
          <button
            key={f.frame_id}
            onClick={() => { setSelected(f); syncRawTexts(f); }}
            className={`w-full text-left px-3 py-2 text-sm transition-colors ${
              selected?.frame_id === f.frame_id
                ? "bg-primary/10 text-primary font-medium"
                : "hover:bg-muted"
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="truncate text-xs">{f.frame_id}: {f.title || "未命名"}</span>
              {f.is_locked && <Lock size={10} className="text-amber-500 shrink-0" />}
            </div>
          </button>
        ))}
      </aside>

      {/* 右侧属性面板 */}
      <main className="flex-1 overflow-y-auto p-6">
        {selected ? (
          <div className="mx-auto max-w-2xl space-y-5">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold">{selected.frame_id} — {selected.title || "未命名帧"}</h3>
              <Button variant="outline" size="sm" onClick={() => handleLock(selected.frame_id, !selected.is_locked)} className="gap-1">
                {selected.is_locked ? <><Unlock size={14} />解锁</> : <><Lock size={14} />锁定</>}
              </Button>
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs">标题</Label>
              <Input value={selected.title} onChange={(e) => setSelected({ ...selected, title: e.target.value })} />
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs">讲解文本</Label>
              <Textarea rows={4} value={selected.narration} onChange={(e) => setSelected({ ...selected, narration: e.target.value })} />
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs">视觉对象 (JSON)</Label>
              <Textarea
                rows={6} className="font-mono text-xs"
                value={visObjText}
                onChange={(e) => {
                  setVisObjText(e.target.value);
                  try { setSelected({ ...selected, visual_objects: JSON.parse(e.target.value) }); setVisObjError(""); }
                  catch { setVisObjError("JSON 格式错误"); }
                }}
              />
              {visObjError && <p className="text-xs text-amber-500">{visObjError}</p>}
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs">状态快照 (JSON)</Label>
              <Textarea
                rows={6} className="font-mono text-xs"
                value={stateSnapText}
                onChange={(e) => {
                  setStateSnapText(e.target.value);
                  try { setSelected({ ...selected, state_snapshot: JSON.parse(e.target.value) }); setStateSnapError(""); }
                  catch { setStateSnapError("JSON 格式错误"); }
                }}
              />
              {stateSnapError && <p className="text-xs text-amber-500">{stateSnapError}</p>}
            </div>

            <div className="flex items-center gap-3 pt-2">
              <Button size="sm" onClick={handleSave} disabled={saving} className="gap-1">
                <Save size={14} /> {saving ? "保存中..." : "保存"}
              </Button>
              <Button size="sm" variant="outline" onClick={handleSaveVersion} className="gap-1">
                <History size={14} /> 保存版本
              </Button>
              {saveMsg && <span className="text-xs text-green-600">{saveMsg}</span>}
            </div>
          </div>
        ) : (
          <div className="flex h-full items-center justify-center text-muted-foreground text-sm">
            选择左侧帧开始编辑
          </div>
        )}
      </main>
    </div>
  );
}

// ============================================================================
// Tab: 导出（原 ExportCenter）
// ============================================================================

const STATUS_LABELS: Record<string, string> = {
  queued: "排队中", rendering: "渲染中", completed: "已完成", failed: "失败",
};

function ExportTabContent({ projectId }: { projectId: string }) {
  const [quality, setQuality] = useState("h");
  const [fps, setFps] = useState("30");
  const [includeSubtitles, setIncludeSubtitles] = useState(true);
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
      } catch { /* ignore */ }
    }, 3000);
  }, []);

  useEffect(() => () => clearInterval(pollRef.current), []);

  const handleCreate = async () => {
    if (!projectId) return;
    setSubmitting(true); setError("");
    try {
      const res = await createExportJob(projectId, {
        quality: quality as "l" | "m" | "h" | "k",
        fps: parseInt(fps, 10),
        include_subtitles: includeSubtitles,
      });
      setJobId(res.job_id);
      startPolling(res.job_id);
    } catch (err) {
      if (err instanceof NetworkError) setError("无法连接到服务器");
      else setError(err instanceof Error ? err.message : "创建导出任务失败");
    } finally { setSubmitting(false); }
  };

  return (
    <div className="mx-auto max-w-2xl p-6">
      <h2 className="text-lg font-bold mb-1">视频导出</h2>
      <p className="text-sm text-muted-foreground mb-6">将推演导出为 Manim 教学视频</p>

      {!jobId && (
        <div className="rounded-xl border p-6 space-y-5">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label className="text-xs">画质</Label>
              <Select value={quality} onValueChange={(v) => setQuality(v ?? "h")}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="l">480p</SelectItem>
                  <SelectItem value="m">720p</SelectItem>
                  <SelectItem value="h">1080p</SelectItem>
                  <SelectItem value="k">4K</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">帧率 (FPS)</Label>
              <Input type="number" value={fps} onChange={(e) => setFps(e.target.value)} min={15} max={60} />
            </div>
          </div>
          <div className="flex items-center justify-between">
            <Label className="text-xs">包含字幕</Label>
            <Switch checked={includeSubtitles} onCheckedChange={(v) => setIncludeSubtitles(v)} />
          </div>
          {error && <p className="text-sm text-red-500 flex items-center gap-1"><AlertTriangle size={14} />{error}</p>}
          <Button onClick={handleCreate} disabled={submitting} className="w-full gap-2">
            <Film size={18} /> {submitting ? "正在创建..." : "开始导出"}
          </Button>
        </div>
      )}

      {job && (
        <div className="rounded-xl border p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold">导出任务</h3>
            <Badge variant={job.status === "completed" ? "default" : "secondary"}>
              {STATUS_LABELS[job.status] ?? job.status}
            </Badge>
          </div>
          <Progress value={job.progress_pct} className="h-2" />
          <p className="text-right text-xs text-muted-foreground">{job.progress_pct.toFixed(0)}%</p>

          {job.status === "failed" && job.error_log && (
            <div className="rounded-lg bg-red-50 p-3 text-sm text-red-600">{job.error_log}</div>
          )}

          {job.status === "completed" && job.artifacts && (
            <div className="space-y-4">
              {job.artifacts.filter((a) => a.type === "mp4").map((a) => (
                <div key={a.type} className="rounded-lg border overflow-hidden bg-black">
                  <video src={a.url} controls className="w-full" style={{ maxHeight: 400 }}>
                    您的浏览器不支持视频播放
                  </video>
                </div>
              ))}
              <div className="space-y-2">
                <p className="text-xs text-muted-foreground">下载文件</p>
                {job.artifacts.map((a) => (
                  <a key={a.type} href={a.url} download className="flex items-center justify-between rounded-lg border p-3 hover:bg-muted transition-colors">
                    <span className="text-sm font-medium">{a.type === "mp4" ? "视频文件 (MP4)" : a.type === "manim_source" ? "Manim 源码 (main.py)" : "字幕 (SRT)"}</span>
                    <Download size={16} className="text-muted-foreground" />
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
