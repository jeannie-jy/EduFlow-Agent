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
import { toUserFacingError } from "@/lib/user-facing-error";
import {
  ArrowLeft,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Sparkles,
  RefreshCw,
  Upload,
  Loader2,
  Trash2,
} from "lucide-react";
import {
  getProject,
  createProject,
  deleteProject,
  startGeneration,
  cancelGeneration,
  forgetProjectStream,
  streamFromUrl,
  approvePlan,
  rejectPlan,
  resumeProjectStream,
  discoverProjectStream,
  listModules,
  type ProjectDetailResponse,
  type SSEProgressEvent,
  type SSEOptions,
  type SSEWaitingApprovalEvent,
  type SSEModuleStartEvent,
  type SSEModuleDoneEvent,
  type SSEModuleErrorEvent,
  type ModuleInfo,
  NetworkError,
  ApiError,
  listMaterials,
  uploadMaterial,
  parseMaterial,
  getBackgroundJob,
  deleteMaterial,
  type MaterialItem,
} from "@/services";
import { recordModelProcessingConsent } from "@/services/account";
import { ModuleSelector } from "@/features/modules/ModuleSelector";
import { ModuleProgress, type ModuleProgressItem } from "@/features/modules/ModuleProgress";
import { ModuleResultsPanel } from "@/features/modules/ModuleResultsPanel";
import { StepIndicator, type StepId } from "@/components/workbench/StepIndicator";

// ============================================================================
// 步骤类型（替代 Tab）
// ============================================================================

type SSEPhase = "idle" | "connecting" | "planning" | "waiting_approval" | "generating" | "validating" | "reviewing" | "done" | "error";

const MATERIAL_PARSE_POLL_INTERVAL_MS = 500;
const MATERIAL_PARSE_MAX_POLLS = 60;

function materialStatusLabel(status: MaterialItem["status"]): string {
  if (status === "uploaded") return "待解析";
  if (status === "parse_queued") return "解析中";
  if (status === "parsed") return "已解析";
  return "解析失败";
}

function formatMaterialSize(sizeBytes: number): string {
  if (sizeBytes < 1024) return `${sizeBytes} B`;
  if (sizeBytes < 1024 * 1024) return `${(sizeBytes / 1024).toFixed(1)} KB`;
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`;
}

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
  }, [projectId, isNew, refreshProject, searchParams]);

  // 确定初始步骤
  useEffect(() => {
    if (isNew) return;
    if (!project?.status) return;
    // The persisted project status is the source of truth for workflow
    // navigation. A completed project may legitimately have no successful
    // module outputs (for example, every selected module failed, or an older
    // project only persisted its teaching plan). In that case the results
    // panel must explain the empty state instead of silently sending the user
    // back to step one while the header still says “已完成”.
    if (project.status === "done") {
      setCurrentStep("results");
      setCompletedSteps(["select", "plan"]);
    } else {
      setCurrentStep("select");
      setCompletedSteps([]);
    }
  }, [project?.status, isNew]);

  // Step 3 时替换 URL（新建模式）
  useEffect(() => {
    if (currentStep === "results" && realIdRef.current && isNew) {
      navigate(`/app/project/${realIdRef.current}`, { replace: true });
    }
  }, [currentStep, isNew, navigate]);

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
    <div className="flex min-h-full flex-col">
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
      <div className="flex-1">
        {projectId && currentStep === "results" && (
          <ModuleResultsPanel
            project={project}
            onRefreshProject={refreshProject}
            onNavigateTab={(step) => setCurrentStep(step as StepId)}
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
  onCreated?: (realId: string | null) => void;
  refreshProject?: () => Promise<void>;
}) {
  const realIdRef = useRef<string | null>(null);
  const [phase, setPhase] = useState<SSEPhase>("idle");
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState("");
  const [teachingPlan, setTeachingPlan] = useState<Record<string, unknown> | null>(null);
  const [qualityReport, setQualityReport] = useState<Record<string, unknown> | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [allowMaterialModelProcessing, setAllowMaterialModelProcessing] = useState(false);
  const [materials, setMaterials] = useState<MaterialItem[]>([]);
  const [selectedMaterialIds, setSelectedMaterialIds] = useState<string[]>([]);
  const [materialError, setMaterialError] = useState<string | null>(null);
  const [uploadingMaterial, setUploadingMaterial] = useState(false);
  const [removingMaterialId, setRemovingMaterialId] = useState<string | null>(null);
  const materialInputRef = useRef<HTMLInputElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const startedRef = useRef(false);
  const generationAttemptRef = useRef(0);
  const resumeAttemptedRef = useRef(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>();
  const [cancelling, setCancelling] = useState(false);

  // 模块选择状态（Phase A）
  const [availableModules, setAvailableModules] = useState<ModuleInfo[]>([]);
  const [selectedModules, setSelectedModules] = useState<string[]>([
    "mindmap", "cards", "quiz", "comparison", "misconception", "pathway", "sandbox",
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
          { module_id: "interactive_demo", display_name: "交互推演", description: "知识互动体验", icon: "play", category: "interactive", priority: 3, estimated_seconds: 40 },
          { module_id: "quiz", display_name: "小练习", description: "自动生成练习题", icon: "quiz", category: "interactive", priority: 4, estimated_seconds: 25 },
          { module_id: "comparison", display_name: "对比分析", description: "按当前主题生成多维度对比", icon: "comparison", category: "visual", priority: 5, estimated_seconds: 30 },
          { module_id: "video", display_name: "教学视频", description: "生成教学视频", icon: "video", category: "export", priority: 6, estimated_seconds: 120 },
          { module_id: "misconception", display_name: "常见误区", description: "识别并澄清常见误解", icon: "misconception", category: "visual", priority: 7, estimated_seconds: 30 },
          { module_id: "pathway", display_name: "学习路径", description: "生成循序渐进的学习路径", icon: "pathway", category: "visual", priority: 8, estimated_seconds: 30 },
          { module_id: "sandbox", display_name: "代码沙箱", description: "提供可运行的代码实验", icon: "sandbox", category: "interactive", priority: 9, estimated_seconds: 45 },
        ]);
      });
  }, [projectId]);

  // 加载当前账户已有课件，上传入口和历史课件共用同一份列表。
  useEffect(() => {
    let cancelled = false;
    listMaterials()
      .then((res) => {
        if (!cancelled) setMaterials(res.items);
      })
      .catch(() => {
        // 课件是可选能力，列表加载失败不应阻塞普通主题生成。
      });
    return () => { cancelled = true; };
  }, [projectId]);

  // 历史项目重新打开时恢复之前选入的材料 ID。
  useEffect(() => {
    if (isNew || !project?.dsl) return;
    const constraints = project.dsl.constraints;
    if (!constraints || typeof constraints !== "object") return;
    const ids = (constraints as { material_ids?: unknown }).material_ids;
    if (Array.isArray(ids)) {
      setSelectedMaterialIds(ids.filter((id): id is string => typeof id === "string"));
    }
  }, [isNew, project?.dsl]);

  const updateMaterialStatus = useCallback((id: string, status: MaterialItem["status"]) => {
    setMaterials((current) => current.map((material) => (
      material.id === id ? { ...material, status } : material
    )));
  }, []);

  const handleParseMaterial = useCallback(async (id: string) => {
    setMaterialError(null);
    updateMaterialStatus(id, "parse_queued");
    try {
      const parse = await parseMaterial(id);
      if (parse.status === "done" || parse.status === "completed") {
        updateMaterialStatus(id, "parsed");
        return true;
      }
      if (!parse.job_id) throw new Error("课件解析任务未创建");

      for (let attempt = 0; attempt < MATERIAL_PARSE_MAX_POLLS; attempt += 1) {
        await new Promise((resolve) => setTimeout(resolve, MATERIAL_PARSE_POLL_INTERVAL_MS));
        const job = await getBackgroundJob(parse.job_id);
        if (job.status === "completed") {
          updateMaterialStatus(id, "parsed");
          return true;
        }
        if (job.status === "failed" || job.status === "cancelled") {
          throw new Error(job.error_code || "课件解析失败");
        }
      }
      throw new Error("课件解析超时，请稍后重试");
    } catch (err) {
      updateMaterialStatus(id, "parse_failed");
      setMaterialError(err instanceof ApiError ? err.message : err instanceof Error ? err.message : "课件解析失败");
      return false;
    }
  }, [updateMaterialStatus]);

  const handleMaterialUpload = useCallback(async (file: File) => {
    setMaterialError(null);
    setUploadingMaterial(true);
    try {
      const uploaded = await uploadMaterial(file);
      const material: MaterialItem = { ...uploaded, status: "uploaded" };
      setMaterials((current) => [material, ...current.filter((item) => item.id !== material.id)]);
      const parsed = await handleParseMaterial(material.id);
      if (parsed) {
        setSelectedMaterialIds((current) => current.includes(material.id) ? current : [...current, material.id]);
      }
    } catch (err) {
      setMaterialError(err instanceof ApiError ? err.message : err instanceof Error ? err.message : "课件上传失败");
    } finally {
      setUploadingMaterial(false);
    }
  }, [handleParseMaterial]);

  const handleRemoveMaterial = useCallback(async (id: string) => {
    setMaterialError(null);
    setRemovingMaterialId(id);
    try {
      await deleteMaterial(id);
      setMaterials((current) => current.filter((material) => material.id !== id));
      setSelectedMaterialIds((current) => current.filter((materialId) => materialId !== id));
    } catch (err) {
      setMaterialError(err instanceof ApiError ? err.message : err instanceof Error ? err.message : "课件删除失败");
    } finally {
      setRemovingMaterialId(null);
    }
  }, []);

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

  const discardCreatedProject = useCallback(async (id: string) => {
    forgetProjectStream(id);
    try {
      await cancelGeneration(id);
    } catch {
      // Deleting the transient project below is authoritative and also
      // cascades its durable streams. Keep going if cancellation raced it.
    }
    await deleteProject(id);
    if (realIdRef.current === id) realIdRef.current = null;
    onCreated?.(null);
  }, [onCreated]);

  useEffect(() => {
    if (isNew || resumeAttemptedRef.current || !project?.status) return;
    if (!new Set(["planning", "generating", "reviewing"]).has(project.status)) return;
    resumeAttemptedRef.current = true;
    startedRef.current = true;
    setPhase("connecting");
    setMessage("正在恢复生成进度…");
    setTeachingPlan((project.teaching_plan as Record<string, unknown> | null) ?? null);
    onStepChange("plan");

    const streamOptions: SSEOptions = {
      onProgress: (event: SSEProgressEvent) => {
        setProgress(event.pct);
        setMessage(event.message || "正在恢复生成进度…");
        if (event.teaching_plan) setTeachingPlan(event.teaching_plan as Record<string, unknown>);
        if (event.phase === "planning") setPhase("planning");
        else if (event.phase === "validating" || event.phase === "quality") setPhase("validating");
        else setPhase("generating");
      },
      onWaitingApproval: (event: SSEWaitingApprovalEvent) => {
        setPhase("waiting_approval");
        setProgress(event.pct);
        setMessage(event.message);
        if (event.teaching_plan) setTeachingPlan(event.teaching_plan as Record<string, unknown>);
      },
      onModuleStart: (event: SSEModuleStartEvent) => {
        setPhase("reviewing");
        setProgress(event.pct);
        setMessage(event.message);
        setModuleStatuses((current) => new Map(current).set(event.module_id, {
          module_id: event.module_id,
          display_name: event.display_name,
          status: "running",
        }));
      },
      onModuleDone: (event: SSEModuleDoneEvent) => {
        setProgress(event.pct);
        setModuleStatuses((current) => new Map(current).set(event.module_id, {
          module_id: event.module_id,
          display_name: event.display_name,
          status: "done",
        }));
      },
      onModuleError: (event: SSEModuleErrorEvent) => {
        setProgress(event.pct);
        setModuleStatuses((current) => new Map(current).set(event.module_id, {
          module_id: event.module_id,
          display_name: event.display_name ?? event.module_id,
          status: "error",
          error: event.error,
        }));
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
        setErrorMsg(event.message || "恢复生成流失败，请重试");
      },
    };

    let cancelled = false;
    let connection = resumeProjectStream(projectId, streamOptions);

    if (!connection) {
      if (project.status === "planning" && project.teaching_plan) {
        startedRef.current = false;
        setPhase("waiting_approval");
        setMessage("教学计划已生成，等待确认");
      } else {
        void discoverProjectStream(projectId, streamOptions)
          .then((discovered) => {
            if (cancelled) {
              discovered?.close();
              return;
            }
            connection = discovered;
            if (discovered) return;
            startedRef.current = false;
            setPhase("error");
            setErrorMsg("未找到可恢复的生成会话，请重新开始生成");
          })
          .catch(() => {
            if (cancelled) return;
            startedRef.current = false;
            setPhase("error");
            setErrorMsg("查询可恢复生成会话失败，请稍后重试");
          });
      }
    }
    return () => {
      cancelled = true;
      connection?.close();
    };
  }, [isNew, project?.status, project?.teaching_plan, projectId, onDone, onStepChange, refreshProject]);

  const handleStart = useCallback(async (selected: string[]) => {
    if (startedRef.current) return;
    const attempt = ++generationAttemptRef.current;
    if (allowMaterialModelProcessing) {
      const pendingMaterial = selectedMaterialIds.some((id) => (
        materials.find((material) => material.id === id)?.status !== "parsed"
      ));
      if (pendingMaterial) {
        setErrorMsg("请等待选中的课件解析完成后再生成");
        return;
      }
    }
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
          constraints: {
            allow_material_model_processing: allowMaterialModelProcessing,
            material_ids: selectedMaterialIds,
          },
        });
        effectiveProjectId = res.id;
        realIdRef.current = res.id;
        onCreated?.(res.id);
        if (attempt !== generationAttemptRef.current) {
          try {
            await discardCreatedProject(res.id);
          } catch (err) {
            setPhase("error");
            setErrorMsg(err instanceof Error ? err.message : "取消后清理临时推演失败");
          }
          return;
        }
      } catch (err) {
        if (attempt !== generationAttemptRef.current) return;
        setPhase("idle");
        startedRef.current = false;
        setErrorMsg(err instanceof NetworkError ? "无法连接到服务器" : err instanceof ApiError ? err.message : "创建失败，请重试");
        return;
      }
    }

    onStepChange("plan");

    try {
      if (allowMaterialModelProcessing) {
        try {
          await recordModelProcessingConsent();
        } catch (err) {
          // Anonymous local-development mode predates the account consent
          // endpoint; production auth-required deployments still fail closed.
          if (!(err instanceof ApiError && err.status === 401)) throw err;
        }
      }
      const generation = await startGeneration(
        effectiveProjectId,
        "modules",
        selected,
        {
          allow_material_model_processing: allowMaterialModelProcessing,
          material_ids: selectedMaterialIds,
        },
      );
      if (attempt !== generationAttemptRef.current) {
        if (isNew && effectiveProjectId) {
          try {
            await discardCreatedProject(effectiveProjectId);
          } catch (err) {
            setPhase("error");
            setErrorMsg(err instanceof Error ? err.message : "取消后清理临时推演失败");
          }
        }
        return;
      }
      abortRef.current?.abort();
      abortRef.current = new AbortController();

      streamFromUrl(generation.stream_url, {
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
      if (attempt !== generationAttemptRef.current) return;
      setPhase("idle");
      startedRef.current = false;
      if (err instanceof NetworkError) setErrorMsg("无法连接到服务器");
      else setErrorMsg(err instanceof Error ? err.message : "生成启动失败");
    }
  }, [projectId, onDone, isNew, title, topic, onStepChange, onCreated, refreshProject, resetTimeout, allowMaterialModelProcessing, selectedMaterialIds, materials, discardCreatedProject]);

  const handleCancelGeneration = useCallback(async () => {
    generationAttemptRef.current += 1;
    abortRef.current?.abort();
    abortRef.current = null;
    if (timeoutRef.current) clearTimeout(timeoutRef.current);

    const effectiveProjectId = realIdRef.current || (!isNew ? projectId : null);
    setCancelling(true);
    setErrorMsg(null);
    try {
      if (effectiveProjectId) {
        if (isNew) {
          await discardCreatedProject(effectiveProjectId);
        } else {
          forgetProjectStream(effectiveProjectId);
          await cancelGeneration(effectiveProjectId);
        }
      }
      setTeachingPlan(null);
      setQualityReport(null);
      setModuleStatuses(new Map());
      setProgress(0);
      setMessage("");
      setPhase("idle");
      startedRef.current = false;
      onStepChange("select");
    } catch (err) {
      setPhase("error");
      setErrorMsg(
        err instanceof NetworkError
          ? "取消生成失败，无法连接到服务器"
          : err instanceof Error
            ? err.message
            : "取消生成失败，请重试",
      );
    } finally {
      setCancelling(false);
    }
  }, [discardCreatedProject, isNew, onStepChange, projectId]);

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
  }, [projectId, onDone, onStepChange, refreshProject, selectedModules]);

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
  }, [onStepChange, projectId]);

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
          <div className="rounded-xl border border-[var(--border)] p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="font-semibold mb-1">添加课件（可选）</h3>
                <p className="text-sm text-muted-foreground">
                  上传 PDF、PPTX、TXT、Markdown 或代码文件，解析后可选入本项目。
                </p>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="shrink-0 gap-2"
                disabled={uploadingMaterial}
                onClick={() => materialInputRef.current?.click()}
              >
                {uploadingMaterial ? <Loader2 size={15} className="animate-spin" /> : <Upload size={15} />}
                {uploadingMaterial ? "上传中…" : "上传课件"}
              </Button>
            </div>
            <input
              ref={materialInputRef}
              type="file"
              className="hidden"
              accept=".pdf,.pptx,.txt,.md,.py,.c,.java,.cpp"
              onChange={(event) => {
                const file = event.target.files?.[0];
                event.target.value = "";
                if (file) void handleMaterialUpload(file);
              }}
            />

            {materialError && (
              <p role="alert" className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950 dark:text-red-300">
                {materialError}
              </p>
            )}

            {materials.length > 0 ? (
              <div className="mt-4 space-y-2">
                {materials.map((material) => {
                  const selected = selectedMaterialIds.includes(material.id);
                  const canSelect = material.status === "parsed";
                  return (
                    <div key={material.id} className="flex items-center justify-between gap-3 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2">
                      <label className="flex min-w-0 items-center gap-3">
                        <input
                          type="checkbox"
                          className="h-4 w-4 shrink-0"
                          checked={selected}
                          disabled={!canSelect}
                          onChange={() => setSelectedMaterialIds((current) => (
                            current.includes(material.id)
                              ? current.filter((id) => id !== material.id)
                              : [...current, material.id]
                          ))}
                        />
                        <span className="min-w-0">
                          <span className="block truncate text-sm font-medium">{material.filename}</span>
                          <span className="block text-xs text-muted-foreground">
                            {formatMaterialSize(material.size_bytes)} · {materialStatusLabel(material.status)}
                          </span>
                        </span>
                      </label>
                      <div className="flex shrink-0 items-center gap-1">
                        {(material.status === "uploaded" || material.status === "parse_failed") && (
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            disabled={uploadingMaterial}
                            onClick={() => void handleParseMaterial(material.id)}
                          >
                            解析
                          </Button>
                        )}
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon-sm"
                          aria-label={`删除 ${material.filename}`}
                          disabled={removingMaterialId === material.id}
                          onClick={() => void handleRemoveMaterial(material.id)}
                        >
                          {removingMaterialId === material.id ? <Loader2 size={15} className="animate-spin" /> : <Trash2 size={15} />}
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="mt-4 rounded-lg border border-dashed border-[var(--border)] px-3 py-3 text-xs text-muted-foreground">
                尚未添加课件。你也可以直接使用下方的通用知识生成内容。
              </p>
            )}
            <p className="mt-3 text-xs text-muted-foreground">
              只有勾选下方授权后，选中的课件片段才会发送给模型；未选中的课件不会参与本次生成。
            </p>
          </div>
          <div className="rounded-xl border border-[var(--border)] p-4">
            <p className="text-sm font-medium text-[var(--foreground)] mb-3">选择产出形式</p>
            <ModuleSelector
              modules={availableModules}
              onStart={handleStart}
              defaultSelected={selectedModules}
            />
          </div>
          <label className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50/60 p-4 text-sm dark:border-amber-900 dark:bg-amber-950/30">
            <input
              type="checkbox"
              className="mt-0.5 h-4 w-4"
              checked={allowMaterialModelProcessing}
              onChange={(event) => setAllowMaterialModelProcessing(event.target.checked)}
            />
            <span>
              <span className="font-medium">允许将本项目选入的课件片段发送给模型</span>
              <span className="mt-1 block text-xs text-muted-foreground">
                仅在你明确勾选时处理材料；数据会发送到你配置的 DeepSeek/阿里百炼账户，并记录本次同意。
              </span>
            </span>
          </label>
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
            <Button
              variant="outline"
              size="sm"
              onClick={() => void handleCancelGeneration()}
              disabled={cancelling}
              className="gap-2"
            >
              {cancelling ? <Loader2 size={16} className="animate-spin" /> : <XCircle size={16} />}
              {cancelling ? "正在取消..." : "取消"}
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
            <p className="text-sm text-green-600">教学计划和所选成果已生成完毕</p>
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
          <h3 className="font-semibold text-red-800 mb-2">{toUserFacingError(errorMsg).title}</h3>
          <p className="text-sm text-red-600 mb-2">{toUserFacingError(errorMsg).message}</p>
          <p className="text-xs text-red-500 mb-6">{toUserFacingError(errorMsg).suggestion}</p>
          <Button variant="outline" onClick={() => { setPhase("idle"); startedRef.current = false; }} className="gap-2">
            <RefreshCw size={16} /> 重试
          </Button>
        </div>
      )}
    </div>
  );
}




