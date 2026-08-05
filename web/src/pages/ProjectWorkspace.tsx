/**
 * 统一项目工作区 — 三步流程（select → plan → results）。
 *
 * GET /app/project/:id
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useSearchParams, useNavigate, Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ArrowLeft,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Sparkles,
  RefreshCw,
} from "lucide-react";
import {
  getProject,
  createProject,
  startGeneration,
  streamGeneration,
  streamFromUrl,
  approvePlan,
  rejectPlan,
  listModules,
  type ProjectDetailResponse,
  type SSEProgressEvent,
  type SSEWaitingApprovalEvent,
  type SSEModuleStartEvent,
  type SSEModuleDoneEvent,
  type SSEModuleErrorEvent,
  type ModuleInfo,
  NetworkError,
  ApiError,
} from "@/services";
import { ModuleSelector } from "@/features/modules/ModuleSelector";
import { ModuleProgress, type ModuleProgressItem } from "@/features/modules/ModuleProgress";
import { ModuleResultsPanel } from "@/features/modules/ModuleResultsPanel";
import { StepIndicator, type StepId } from "@/components/workbench/StepIndicator";

// ============================================================================
// 步骤类型（替代 Tab）
// ============================================================================

type SSEPhase = "idle" | "connecting" | "planning" | "waiting_approval" | "generating" | "validating" | "reviewing" | "done" | "error";

export function ProjectWorkspace() {
  const { projectId } = useParams<{ projectId: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const isNew = projectId === "_new";
  const realIdRef = useRef<string | null>(null);

  const [project, setProject] = useState<ProjectDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [currentStep, setCurrentStep] = useState<StepId>("select");
  const [completedSteps, setCompletedSteps] = useState<StepId[]>([]);
  const [title, setTitle] = useState("");
  const [topic, setTopic] = useState("");

  // 加载 / 刷新项目
  const refreshProject = useCallback(async () => {
    if (!projectId || isNew) return;
    try {
      const data = await getProject(projectId);
      setProject(data);
    } catch { /* ignore */ }
  }, [projectId, isNew]);

  useEffect(() => {
    if (isNew) {
      setLoading(false);
      const t = searchParams.get("template") ?? "";
      if (t) setTopic(`讲解 ${t}，包括核心概念、工作原理和典型示例。`);
      return;
    }
    if (!projectId) return;
    setLoading(true);
    refreshProject().finally(() => setLoading(false));
  }, [projectId, isNew]);

  // 确定初始步骤
  useEffect(() => {
    if (isNew) return;
    if (!project?.status) return;
    if (project.status === "done") {
      setCurrentStep("results");
      setCompletedSteps(["select", "plan"]);
    }
  }, [project?.status, project?.module_outputs, isNew]);

  // Step 3 时替换 URL（新建模式）
  useEffect(() => {
    if (currentStep === "results" && realIdRef.current && isNew) {
      navigate(`/app/project/${realIdRef.current}`, { replace: true });
    }
  }, [currentStep, isNew]);

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
               project.status === "failed" ? "生成失败" :
               project.status === "draft" ? "草稿" :
               project.status === "planning" ? "规划中" :
               project.status === "generating" ? "生成中" :
               project.status === "reviewing" ? "校验中" : project.status}
            </Badge>
          )}
        </div>

        {/* 右侧快捷操作 */}
        <div className="flex items-center gap-1.5 shrink-0" />
      </header>

      {/* 步骤指示器 */}
      <StepIndicator current={currentStep} completed={completedSteps} />

      {/* 内容区 */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        {projectId && currentStep === "results" && (
          <ModuleResultsPanel
            project={project}
          />
        )}
        {projectId && currentStep !== "results" && (
          <PlanTabContent
            projectId={projectId}
            project={project}
            currentStep={currentStep}
            onStepChange={(step: StepId) => {
              setCurrentStep(step);
              if (step === "plan") setCompletedSteps((p) => [...new Set<StepId>([...p, "select"])]);
              if (step === "results") setCompletedSteps((p) => [...new Set<StepId>([...p, "select", "plan"])]);
            }}
            onDone={() => {
              void refreshProject().then(() => {
                setCurrentStep("results");
                setCompletedSteps(["select", "plan"]);
              });
            }}
            isNew={isNew}
            title={title}
            topic={topic}
            setTitle={setTitle}
            setTopic={setTopic}
            onCreated={(realId) => { realIdRef.current = realId; }}
            refreshProject={refreshProject}
          />
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Tab: 计划（原 PlanConfirm）— 三步流程中的 select + plan 步骤
// ============================================================================

function PlanTabContent({ projectId, project, currentStep, onStepChange, onDone, isNew, title, topic, setTitle, setTopic, onCreated, refreshProject }: {
  projectId: string;
  project: ProjectDetailResponse | null;
  currentStep: StepId;
  onStepChange: (step: StepId) => void;
  onDone: () => void;
  isNew: boolean;
  title: string;
  topic: string;
  setTitle: (v: string) => void;
  setTopic: (v: string) => void;
  onCreated?: (realId: string) => void;
  refreshProject?: () => Promise<void>;
}) {
  const realIdRef = useRef<string | null>(null);
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
  const [selectedModules, setSelectedModules] = useState<string[]>([
    "mindmap", "cards", "frames", "quiz", "comparison", "misconception", "pathway", "sandbox",
    "interactive_demo", "video",
  ]);
  const [moduleStatuses, setModuleStatuses] = useState<Map<string, ModuleProgressItem>>(new Map());

  // 加载可用模块列表（idle 阶段）
  useEffect(() => {
    if (!projectId) return;
    listModules(projectId)
      .then((res) => setAvailableModules(res.modules))
      .catch(() => {
        // 回退：硬编码模块列表（保证至少基本模块可用）
        setAvailableModules([
          { module_id: "mindmap", display_name: "思维导图", description: "知识概念导图", icon: "mindmap", category: "visual", priority: 1, estimated_seconds: 15 },
          { module_id: "cards", display_name: "知识卡片", description: "概念知识卡片", icon: "cards", category: "visual", priority: 2, estimated_seconds: 20 },
          { module_id: "frames", display_name: "推演脚本", description: "结构化教学推演脚本（逐帧DSL）", icon: "play", category: "interactive", priority: 3, estimated_seconds: 40 },
          { module_id: "quiz", display_name: "小练习", description: "自动生成练习题", icon: "quiz", category: "interactive", priority: 4, estimated_seconds: 25 },
          { module_id: "comparison", display_name: "算法对比", description: "多维度算法对比", icon: "comparison", category: "visual", priority: 5, estimated_seconds: 30 },
        ]);
      });
  }, [projectId]);

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

  const handleStart = useCallback(async (selected: string[]) => {
    if (startedRef.current) return;
    startedRef.current = true;
    setSelectedModules(selected);
    setPhase("connecting");
    setErrorMsg(null);
    resetTimeout();

    let effectiveProjectId = projectId;

    if (isNew) {
      try {
        const finalTitle = title.trim() || topic.trim().slice(0, 30) || "未命名推演";
        const res = await createProject({
          title: finalTitle,
          input_content: topic.trim(),
          audience: "undergraduate_cs",
          difficulty: "intermediate",
        });
        effectiveProjectId = res.id;
        realIdRef.current = res.id;
        onCreated?.(res.id);
      } catch (err) {
        setPhase("idle");
        startedRef.current = false;
        setErrorMsg(err instanceof NetworkError ? "无法连接到服务器" : err instanceof ApiError ? err.message : "创建失败，请重试");
        return;
      }
    }

    onStepChange("plan");

    try {
      await startGeneration(effectiveProjectId, "modules", selected);
      abortRef.current?.abort();
      abortRef.current = new AbortController();

      streamGeneration(effectiveProjectId, {
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
        onDone: async (event) => {
          setPhase("done");
          setProgress(100);
          setMessage("生成完成");
          if (event.quality_report) setQualityReport(event.quality_report as Record<string, unknown>);
          if (refreshProject) await refreshProject();
          onStepChange("results");
          onDone();
        },
        onError: (event) => {
          setPhase("error");
          setErrorMsg(event.message || "生成过程中发生错误");
        },
      });
    } catch (err) {
      setPhase("idle");
      startedRef.current = false;
      if (err instanceof NetworkError) setErrorMsg("无法连接到服务器");
      else setErrorMsg(err instanceof Error ? err.message : "生成启动失败");
    }
  }, [projectId, onDone, isNew, title, topic, onStepChange, onCreated, resetTimeout]);

  useEffect(() => {
    return () => { abortRef.current?.abort(); };
  }, []);

  // ── 审批操作 ─────────────────────────────────────────────────
  const handleApprove = useCallback(async () => {
    const pid = realIdRef.current || projectId;
    if (!pid) return;
    try {
      const res = await approvePlan(pid, selectedModules.length > 0 ? selectedModules : undefined);
      setPhase("reviewing");
      setErrorMsg(null);
      abortRef.current?.abort();
      abortRef.current = new AbortController();
      streamFromUrl(res.stream_url, {
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
        onProgress: (event: SSEProgressEvent) => {
          setProgress(event.pct);
          setMessage(event.message);
        },
        onDone: async () => {
          setPhase("done");
          setProgress(100);
          setMessage("模块生成完成");
          if (refreshProject) await refreshProject();
          onStepChange("results");
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
      else setErrorMsg(err instanceof Error ? err.message : "批准失败");
    }
  }, [projectId, onDone, selectedModules]);

  const handleReject = useCallback(async (feedback: string) => {
    const pid = realIdRef.current || projectId;
    if (!pid) return;
    try {
      const res = await rejectPlan(pid, feedback);
      streamFromUrl(res.stream_url, {
        onDone: () => {},
        onError: () => {},
      });
      setPhase("planning");
      startedRef.current = false;
      setMessage("已返回修改，正在根据反馈重新规划...");
      onStepChange("plan");
    } catch (err) {
      if (err instanceof NetworkError) setErrorMsg("无法连接到服务器");
      else setErrorMsg(err instanceof Error ? err.message : "提交失败");
    }
  }, [projectId]);

  return (
    <div className="mx-auto max-w-3xl p-6">
      <h2 className="text-lg font-bold mb-1">
        {currentStep === "select" ? "选择模块" : currentStep === "plan" ? "教学计划" : "成果预览"}
      </h2>
      <p className="text-sm text-muted-foreground mb-6">{project?.title}</p>

      {phase === "idle" && (
        <div className="space-y-6">
          {errorMsg && (
            <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300">
              {errorMsg}
            </div>
          )}
          {isNew && (
            <div className="rounded-xl border border-[var(--border)] p-6">
              <h3 className="font-semibold mb-3">推演标题 *</h3>
              <input
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-4 py-3 text-sm"
                placeholder="例如：Dijkstra 最短路径算法"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>
          )}
          <div className="rounded-xl border border-[var(--border)] p-6">
            <h3 className="font-semibold mb-3">输入教学主题</h3>
            <p className="text-sm text-muted-foreground mb-4">
              描述你想讲解的 CS 知识点，AI 将制定教学计划并生成所选产物
            </p>
            <textarea
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-4 py-3 text-sm resize-none"
              rows={3}
              placeholder="例如：Dijkstra 最短路径算法的工作原理和正确性证明"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
            />
          </div>
          <div className="rounded-xl border border-[var(--border)] p-4">
            <p className="text-sm font-medium text-[var(--foreground)] mb-3">选择产出形式</p>
            <ModuleSelector
              modules={availableModules}
              onStart={handleStart}
              defaultSelected={selectedModules}
            />
          </div>
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

          {/* 反悔机制：可折叠模块微调 */}
          <details className="rounded-xl border border-[var(--border)] p-4">
            <summary className="cursor-pointer text-sm text-[var(--muted-foreground)]">
              已选 {selectedModules.length} 个模块 · 点击调整
            </summary>
            <div className="mt-3">
              <ModuleSelector
                modules={availableModules}
                onStart={(ids) => setSelectedModules(ids)}
                defaultSelected={selectedModules}
                showStartButton={false}
              />
            </div>
          </details>

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





      {phase === "reviewing" && (
        <div className="space-y-6">
          <div className="rounded-xl border p-6">
            <div className="flex items-center gap-3 mb-4">
              <Sparkles size={20} className="text-primary animate-pulse" />
              <div>
                <p className="font-medium">正在生成模块产物...</p>
                <p className="text-sm text-muted-foreground">{message}</p>
              </div>
            </div>
            <Progress value={progress} className="mb-4 h-2" />
            {moduleStatuses.size > 0 && (
              <ModuleProgress
                modules={[...moduleStatuses.values()]}
                totalPct={progress}
              />
            )}
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




