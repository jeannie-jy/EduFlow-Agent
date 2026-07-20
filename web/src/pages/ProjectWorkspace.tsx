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
  Pencil,
  Save,
  Lock,
  Unlock,
  History,
  Film,
  Download,
  Layers,
  FileText,
  Settings2,
} from "lucide-react";
import {
  getProject,
  startGeneration,
  streamGeneration,
  listFrames,
  updateFrame,
  lockFrame,
  regenerate,
  listParameters,
  saveVersion,
  listVersions,
  restoreVersion,
  createExportJob,
  getExportStatus,
  type ProjectDetailResponse,
  type FrameData,
  type SSEProgressEvent,
  type ExportJobResponse,
  type VersionItem,
  ApiError,
  NetworkError,
} from "@/services";
import { FeedbackPanel } from "@/components/FeedbackPanel";

// ============================================================================
// Tab 类型
// ============================================================================

type ProjectTab = "plan" | "play" | "edit" | "export";

const TABS: { key: ProjectTab; label: string; icon: typeof Sparkles }[] = [
  { key: "plan", label: "计划", icon: Sparkles },
  { key: "play", label: "推演", icon: Play },
  { key: "edit", label: "编辑", icon: Pencil },
  { key: "export", label: "导出", icon: Film },
];

const STATUS_DEFAULT_TAB: Record<string, ProjectTab> = {
  draft: "plan",
  planning: "plan",
  generating: "plan",
  reviewing: "play",
  done: "play",
};

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
  const activeTab: ProjectTab =
    TABS.some((t) => t.key === tabFromUrl) ? tabFromUrl
    : project?.status ? (STATUS_DEFAULT_TAB[project.status] ?? "plan")
    : "plan";

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

type SSEPhase = "idle" | "connecting" | "planning" | "generating" | "validating" | "done" | "error";

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

  // 连接超时检测：15 秒内无进展 → 报错
  const resetTimeout = useCallback(() => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => {
      setPhase((prev) => {
        if (prev === "connecting") {
          setErrorMsg("连接超时，请确认后端服务已启动（http://localhost:8000）");
          return "error";
        }
        return prev;
      });
    }, 15000);
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
      await startGeneration(projectId, "full");
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

  return (
    <div className="mx-auto max-w-3xl p-6">
      <h2 className="text-lg font-bold mb-1">教学计划</h2>
      <p className="text-sm text-muted-foreground mb-6">{project?.title}</p>

      {phase === "idle" && (
        <div className="rounded-xl border p-8 text-center">
          <Sparkles size={48} className="mx-auto mb-4 text-indigo-400" />
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
// Tab: 推演（原 Player）
// ============================================================================

function PlayTabContent({ projectId, project }: {
  projectId: string;
  project: ProjectDetailResponse | null;
}) {
  const [frames, setFrames] = useState<FrameData[]>([]);
  const [paramCount, setParamCount] = useState(0);

  useEffect(() => {
    if (!projectId) return;
    Promise.all([
      listFrames(projectId),
      listParameters(projectId),
    ]).then(([fd, pd]) => {
      setFrames(fd.frames ?? []);
      setParamCount((pd as { parameters?: unknown[] }).parameters?.length ?? 0);
    }).catch(() => {});
  }, [projectId]);

  const dsl = project?.dsl as Record<string, unknown> | undefined;
  const dslFrames = (dsl?.frames as Record<string, unknown>[]) ?? frames;
  const dslParams = (dsl?.parameters as Record<string, unknown>[]) ?? [];
  const teachingStrategy = dsl?.teaching_strategy as Record<string, unknown> | undefined;
  const qualityReport = project?.quality_report as Record<string, unknown> | undefined;
  const overallScore = qualityReport?.overall_score as number | undefined;
  const displayFrames = dslFrames.length > 0 ? dslFrames : frames;

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
    <div className="p-6">
      {/* 概览卡片 */}
      <div className="grid gap-4 md:grid-cols-4 mb-6">
        <StatCard icon={Layers} label="推演帧" value={String(displayFrames.length)} sub={`${dslParams.length} 个参数`} />
        <StatCard icon={FileText} label="教学目标" value={`${(teachingStrategy?.objectives as string[])?.length ?? 0} 个`} />
        <StatCard icon={Settings2} label="难度" value={project?.difficulty === "intermediate" ? "中级" : project?.difficulty ?? "—"} />
        <StatCard icon={CheckCircle2} label="质量评分" value={overallScore != null ? `${(overallScore * 100).toFixed(0)}%` : "—"} />
      </div>

      {/* 帧列表 */}
      <h3 className="text-sm font-semibold mb-3">帧序列</h3>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {displayFrames.slice(0, 16).map((frame: any, idx: number) => (
          <div key={frame.frame_id ?? idx} className="rounded-lg border p-3">
            <div className="flex items-center justify-between mb-1">
              <Badge variant="outline" className="text-[10px] font-mono">{frame.frame_id ?? `f_${idx + 1}`}</Badge>
              <span className="text-[10px] text-muted-foreground">
                {(frame.visual_objects as any[])?.length ?? 0} 对象
              </span>
            </div>
            <p className="text-sm font-medium truncate">{frame.title ?? "未命名"}</p>
            <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{frame.narration ?? ""}</p>
          </div>
        ))}
      </div>

      {/* 参数列表 */}
      {dslParams.length > 0 && (
        <>
          <h3 className="text-sm font-semibold mt-6 mb-3">可调参数</h3>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {dslParams.map((p: any) => (
              <div key={p.key} className="flex items-center justify-between rounded-lg border bg-muted/30 px-3 py-2">
                <div>
                  <p className="text-sm font-medium">{p.label ?? p.key}</p>
                  <p className="text-[10px] text-muted-foreground">{p.param_type}</p>
                </div>
                <Badge variant="secondary" className="text-[10px]">{String(p.default_value ?? "—").slice(0, 12)}</Badge>
              </div>
            ))}
          </div>
        </>
      )}

      {/* 反馈 */}
      <div className="mt-6 max-w-md">
        <FeedbackPanel projectId={projectId} />
      </div>
    </div>
  );
}

function StatCard({ icon: Icon, label, value, sub }: {
  icon: typeof Layers;
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="rounded-xl border p-4">
      <div className="flex items-center gap-2 mb-1.5">
        <Icon size={15} className="text-primary" />
        <span className="text-xs text-muted-foreground">{label}</span>
      </div>
      <p className="text-xl font-bold tabular-nums">{value}</p>
      {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
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

  useEffect(() => {
    if (!projectId) return;
    setLoading(true);
    listFrames(projectId)
      .then((res) => {
        setFrames(res.frames);
        if (res.frames.length > 0) setSelected(res.frames[0]);
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
    try { await regenerate(projectId, { type: "from_frame" }); } catch { /* ignore */ }
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
            onClick={() => setSelected(f)}
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
                value={JSON.stringify(selected.visual_objects, null, 2)}
                onChange={(e) => { try { setSelected({ ...selected, visual_objects: JSON.parse(e.target.value) }); } catch {} }}
              />
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs">状态快照 (JSON)</Label>
              <Textarea
                rows={6} className="font-mono text-xs"
                value={JSON.stringify(selected.state_snapshot, null, 2)}
                onChange={(e) => { try { setSelected({ ...selected, state_snapshot: JSON.parse(e.target.value) }); } catch {} }}
              />
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
        include_subtitles: includeSubtitles === "true",
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
            <Switch checked={includeSubtitles === "true"} onCheckedChange={(v) => setIncludeSubtitles(v ? "true" : "false")} />
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
            <div className="space-y-2">
              {job.artifacts.map((a) => (
                <a key={a.type} href={a.url} download className="flex items-center justify-between rounded-lg border p-3 hover:bg-muted transition-colors">
                  <span className="text-sm font-medium">{a.type === "mp4" ? "视频文件" : a.type === "manim_source" ? "源码" : "字幕"}</span>
                  <Download size={16} className="text-muted-foreground" />
                </a>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}