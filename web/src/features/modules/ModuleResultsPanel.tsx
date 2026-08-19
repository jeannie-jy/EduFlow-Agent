/**
 * ModuleResultsPanel — 模块成果聚合展示面板。
 *
 * 读取 module_outputs，按模块分类渲染对应的展示组件。
 * 对齐 DESIGN.md：纸本质感、语义色、编辑式排版、章节编号。
 */

import { Brain, Layers, PenTool, Play, Video, GitCompare, AlertTriangle, Map, Code2, CheckCircle2, FolderKanban } from "lucide-react";
import { MisconceptionGallery } from "@/components/workbench/MisconceptionGallery";
import type { MisconceptionItem } from "@/components/workbench/MisconceptionGallery";
import { LearningPathway } from "@/components/workbench/LearningPathway";
import type { PathwayData } from "@/components/workbench/LearningPathway";
import { CodeSandbox } from "@/components/workbench/CodeSandbox";
import type { SandboxData } from "@/components/workbench/CodeSandbox";
import { ComparisonView } from "@/components/workbench/ComparisonView";
import type { ComparisonData } from "@/components/workbench/ComparisonView";
import { QuizPanel } from "@/components/workbench/QuizPanel";
import type { QuizQuestion } from "@/components/workbench/QuizPanel";
import { KnowledgeCardDeck } from "@/components/workbench/KnowledgeCardDeck";
import type { KnowledgeCardData } from "@/components/workbench/KnowledgeCard";
import { MindmapView, type MindmapNode } from "@/components/workbench/MindmapView";
import type { ProjectDetailResponse } from "@/services/projects";
import { useState, useCallback, useEffect } from "react";
import { RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { regenerateModule } from "@/services/generate";
import type { SSEModuleDoneEvent } from "@/services/sse";
import { normalizeFramesArtifact, normalizeVideoArtifact } from "@/features/artifacts/artifact-model";
import { VideoStudioCard } from "@/features/artifacts/VideoStudioCard";
import { InteractiveExperience } from "@/features/artifacts/InteractiveExperience";
import { toUserFacingError } from "@/lib/user-facing-error";

// ============================================================================
// 模块配置
// ============================================================================

const SECTION_CONFIG: Record<string, { title: string; icon: typeof Brain; order: number }> = {
  mindmap:   { title: "思维导图",   icon: Brain,          order: 1 },
  cards:     { title: "知识卡片",   icon: Layers,         order: 2 },
  quiz:      { title: "小练习",     icon: PenTool,        order: 4 },
  comparison:{ title: "对比分析",   icon: GitCompare,     order: 5 },
  misconception: { title: "常见误区", icon: AlertTriangle, order: 6 },
  pathway:   { title: "学习路径",   icon: Map,            order: 7 },
  sandbox:   { title: "代码沙箱",   icon: Code2,          order: 8 },
  interactive_demo: { title: "交互推演", icon: Play, order: 3 },
  video:     { title: "教学视频",   icon: Video,          order: 10 },
};

export interface ModuleResultsPanelProps {
  project: ProjectDetailResponse | null;
  onNavigateTab?: (tab: string) => void;
  onRefreshProject?: () => void | Promise<void>;
}

export function ModuleResultsPanel({ project, onNavigateTab }: ModuleResultsPanelProps) {
  const moduleOutputs = (project?.module_outputs ?? {}) as Record<string, unknown>;
  const persistedErrors = ((project?.dsl?.module_errors ?? {}) as Record<string, unknown>);
  const [localOutputs, setLocalOutputs] = useState<Record<string, unknown>>(moduleOutputs);
  const [localErrors, setLocalErrors] = useState<Record<string, string>>(() =>
    Object.fromEntries(Object.entries(persistedErrors).map(([key, value]) => [key, String(value)])),
  );
  const [isRegenerating, setIsRegenerating] = useState<Record<string, boolean>>({});
  const [targetFrameId, setTargetFrameId] = useState<string>();
  const [navigationMessage, setNavigationMessage] = useState<{ tone: "success" | "error"; text: string }>();

  useEffect(() => {
    setLocalOutputs((project?.module_outputs ?? {}) as Record<string, unknown>);
    const errors = ((project?.dsl?.module_errors ?? {}) as Record<string, unknown>);
    setLocalErrors(Object.fromEntries(Object.entries(errors).map(([key, value]) => [key, String(value)])));
  }, [project?.module_outputs, project?.updated_at]);

  const displayedOutputs = { ...moduleOutputs, ...localOutputs };
  const visibleKeys = new Set([
    ...Object.keys(displayedOutputs),
    ...Object.keys(localErrors),
    ...(project?.selected_modules ?? []),
  ]);
  const entries = [...visibleKeys].map((key) => [key, displayedOutputs[key]] as const);
  const [activeModule, setActiveModule] = useState<string>(() => entries[0]?.[0] ?? "");
  const sorted = entries
    .map(([key, value]) => ({ key, value, error: localErrors[key], config: SECTION_CONFIG[key] }))
    .filter((entry) => entry.config)
    .sort((left, right) => left.config.order - right.config.order);
  const selected = sorted.find((entry) => entry.key === activeModule) ?? sorted[0];
  const selectedVideo = selected?.key === "video" ? normalizeVideoArtifact(selected.value) : null;
  const selectedStatusLabel = selected?.error
    ? "生成失败"
    : selectedVideo && !selectedVideo.job_id
      ? "分镜已就绪"
      : "已生成";

  useEffect(() => {
    if (selected && selected.key !== activeModule) setActiveModule(selected.key);
  }, [activeModule, selected]);

  const handleRegenerate = useCallback((moduleId: string) => {
    if (!project?.id || isRegenerating[moduleId]) return;
    setIsRegenerating((p) => ({ ...p, [moduleId]: true }));

    regenerateModule(project.id, moduleId, {
      onModuleDone: (event: SSEModuleDoneEvent) => {
        setLocalOutputs((prev) => ({ ...prev, [event.module_id]: event.output }));
        setLocalErrors((prev) => {
          const next = { ...prev };
          delete next[event.module_id];
          return next;
        });
        setIsRegenerating((p) => ({ ...p, [moduleId]: false }));
      },
      onModuleError: (event) => {
        setLocalErrors((prev) => ({ ...prev, [event.module_id]: event.error }));
        setIsRegenerating((p) => ({ ...p, [moduleId]: false }));
      },
    });
  }, [project?.id, isRegenerating]);

  const handleFrameNavigate = useCallback((frameId: string) => {
    const framesArtifact = normalizeFramesArtifact(displayedOutputs.frames);
    const target = framesArtifact.frames.find((frame) => frame.frame_id === frameId);

    if (!target) {
      setNavigationMessage({
        tone: "error",
        text: `未找到关联帧 ${frameId}，可能需要重新生成推演脚本。`,
      });
      return;
    }

    if (!displayedOutputs.video) {
      setNavigationMessage({ tone: "error", text: "教学视频尚未生成，暂时无法打开关联分镜。" });
      return;
    }

    setTargetFrameId(frameId);
    setActiveModule("video");
    setNavigationMessage({ tone: "success", text: `已在教学视频中定位到 ${frameId} · ${target.title}` });
  }, [displayedOutputs.frames, displayedOutputs.video]);

  if (sorted.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 p-12 text-center">
        <Layers size={48} className="text-[var(--muted-foreground)]" />
        <div>
          <h3 className="text-lg font-bold text-[var(--foreground)]">尚未生成模块产物</h3>
          <p className="mt-1 text-sm text-[var(--muted-foreground)]">
            请先在「计划」中生成教学计划，选择想要的产出模块后开始生成
          </p>
        </div>
        {onNavigateTab && (
          <Button onClick={() => onNavigateTab("plan")} variant="outline" className="mt-2">
            前往计划
          </Button>
        )}
      </div>
    );
  }

  return (
    <div className="grid min-h-full bg-[var(--background)] lg:grid-cols-[15rem_minmax(0,1fr)]">
      <aside className="border-b border-[var(--border)] bg-[var(--card)] lg:border-b-0 lg:border-r">
        <div className="border-b border-[var(--border)] px-4 py-4">
          <div className="flex items-center gap-2">
            <FolderKanban size={16} className="text-[var(--interactive)]" />
            <h2 className="text-sm font-bold">教学成果</h2>
          </div>
          <p className="mt-1 text-xs text-[var(--muted-foreground)]">
            {sorted.filter((entry) => entry.value != null).length} 个已生成
            {sorted.some((entry) => entry.error) && ` · ${sorted.filter((entry) => entry.error).length} 个失败`}
          </p>
        </div>
        <nav aria-label="成果模块" className="flex gap-1 overflow-x-auto p-2 lg:block lg:space-y-1">
          {sorted.map(({ key, config }) => {
            const SectionIcon = config.icon;
            const active = selected?.key === key;
            return (
              <button
                key={key}
                onClick={() => setActiveModule(key)}
                className={`flex min-w-max items-center gap-2 rounded-lg px-3 py-2 text-left text-xs transition-colors lg:w-full ${
                  active
                    ? "bg-[var(--interactive)]/10 font-semibold text-[var(--interactive)]"
                    : "text-[var(--muted-foreground)] hover:bg-[var(--secondary)] hover:text-[var(--foreground)]"
                }`}
              >
                <SectionIcon size={15} />
                <span className="flex-1">{config.title}</span>
                {isRegenerating[key]
                  ? <RefreshCw size={12} className="animate-spin" />
                  : localErrors[key]
                    ? <AlertTriangle size={12} className="text-[var(--error)]" />
                    : <CheckCircle2 size={12} />}
              </button>
            );
          })}
        </nav>
      </aside>

      {selected && (
        <main className="min-w-0">
          <header className="flex flex-wrap items-center gap-3 border-b border-[var(--border)] bg-[var(--card)] px-4 py-3">
            <selected.config.icon size={17} className="text-[var(--interactive)]" />
            <div className="min-w-0">
              <h2 className="text-sm font-bold">{selected.config.title}</h2>
              <p className="text-[11px] text-[var(--muted-foreground)]">
                {selected.key === "video" ? "检查分镜并按需开始制作视频" : "成果工作区 · 可检查并重新生成当前模块"}
              </p>
            </div>
            <div className="ml-auto flex items-center gap-2">
              <Badge variant="outline" className="text-[10px]">{selectedStatusLabel}</Badge>
              {selected.key !== "video" && (
                <Button
                  variant="outline"
                  size="sm"
                  disabled={isRegenerating[selected.key]}
                  onClick={() => handleRegenerate(selected.key)}
                >
                  <RefreshCw className={isRegenerating[selected.key] ? "animate-spin" : ""} />
                  {isRegenerating[selected.key] ? "生成中" : "重新生成"}
                </Button>
              )}
            </div>
          </header>
          {navigationMessage && (
            <div
              role="status"
              className={`flex items-center justify-between gap-3 border-b px-4 py-2 text-xs ${
                navigationMessage.tone === "error"
                  ? "border-[color-mix(in_oklch,var(--error)_25%,var(--border))] bg-[color-mix(in_oklch,var(--error)_8%,var(--card))] text-[var(--error)]"
                  : "border-[color-mix(in_oklch,var(--success)_25%,var(--border))] bg-[color-mix(in_oklch,var(--success)_8%,var(--card))] text-[var(--foreground)]"
              }`}
            >
              <span>{navigationMessage.text}</span>
              <button
                type="button"
                className="shrink-0 rounded px-2 py-1 text-[var(--muted-foreground)] hover:bg-[var(--secondary)] hover:text-[var(--foreground)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--interactive)]"
                onClick={() => setNavigationMessage(undefined)}
              >
                关闭
              </button>
            </div>
          )}
          <div className="min-w-0">
            {selected.error ? (() => {
              const friendlyError = toUserFacingError(selected.error);
              return (
              <div className="m-4 rounded-lg border border-[color-mix(in_oklch,var(--error)_30%,var(--border))] bg-[color-mix(in_oklch,var(--error)_6%,var(--card))] p-6">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="mt-0.5 shrink-0 text-[var(--error)]" size={20} />
                  <div>
                    <h3 className="font-semibold">{friendlyError.title}</h3>
                    <p className="mt-2 text-sm leading-6 text-[var(--foreground)]">{friendlyError.message}</p>
                    <p className="mt-3 text-xs leading-5 text-[var(--muted-foreground)]">{friendlyError.suggestion}</p>
                  </div>
                </div>
              </div>);
            })() : renderModuleContent(
              selected.key,
              selected.value,
              displayedOutputs.frames,
              project?.id,
              handleFrameNavigate,
              targetFrameId,
              project?.title,
            )}
          </div>
        </main>
      )}
    </div>
  );
}

function renderModuleContent(
  moduleId: string,
  value: unknown,
  framesValue?: unknown,
  projectId?: string,
  onFrameNavigate?: (frameId: string) => void,
  targetFrameId?: string,
  projectTitle?: string,
): React.ReactNode {
  switch (moduleId) {
    case "mindmap":
      // root 结构由 LLM 产出，运行时由 MindmapView 递归渲染；此处仅做类型断言
      return <MindmapView root={normalizeMindmapNode((value as { root?: Record<string, unknown> })?.root)} onFrameClick={onFrameNavigate} />;
    case "cards":
      return <KnowledgeCardDeck cards={((value as { cards?: Array<Record<string, unknown>> })?.cards ?? []).map(
        (card, index): KnowledgeCardData => ({
          id: String(card.id ?? `card-${index + 1}`),
          title: String(card.title ?? `知识卡片 ${index + 1}`),
          definition: card.definition ? String(card.definition) : undefined,
          intuition: card.intuition ? String(card.intuition) : undefined,
          pitfalls: Array.isArray(card.pitfalls) ? card.pitfalls.map(String) : [],
          formula: card.formula ? String(card.formula) : undefined,
          pseudocode: card.pseudocode ? String(card.pseudocode) : undefined,
          relatedFrameIds: Array.isArray(card.related_frame_ids) ? card.related_frame_ids.map(String) : [],
          category: card.category ? String(card.category) : undefined,
          difficulty: typeof card.difficulty === "number" ? card.difficulty : undefined,
        })
      )} onFrameClick={onFrameNavigate} />;
    case "quiz":
      return <QuizPanel questions={(value as { questions?: QuizQuestion[] })?.questions ?? []} />;
    case "video":
      return <VideoStudioCard key={projectId} videoValue={value} framesValue={framesValue} projectId={projectId} targetFrameId={targetFrameId} />;
    case "comparison":
      return <ComparisonView data={value as ComparisonData} />;
    case "misconception":
      return <MisconceptionGallery items={(value as { items?: MisconceptionItem[] })?.items ?? []} />;
    case "pathway":
      return <LearningPathway data={value as PathwayData} />;
    case "sandbox":
      return <CodeSandbox data={value as SandboxData} />;
    case "interactive_demo":
      return renderInteractiveDemo(value, projectTitle);
    default:
      return (
        <div className="p-4 text-sm text-[var(--muted-foreground)]">
          <pre className="max-h-32 overflow-auto text-xs">{JSON.stringify(value, null, 2)}</pre>
        </div>
      );
  }
}

function renderInteractiveDemo(value: unknown, projectTitle?: string): React.ReactNode {
  const code = String((value as Record<string, unknown>)?.code ?? "");
  return <InteractiveExperience code={code} topic={projectTitle} />;
}

function normalizeMindmapNode(
  source?: Record<string, unknown>,
  path: number[] = [0],
  usedIds = new Set<string>(),
): MindmapNode {
  const requestedId = source?.id ? String(source.id) : `mindmap-${path.join("-")}`;
  let id = requestedId;
  let suffix = 2;
  while (usedIds.has(id)) id = `${requestedId}-${suffix++}`;
  usedIds.add(id);

  const children = Array.isArray(source?.children)
    ? source.children.map((child, index) => normalizeMindmapNode(
        child as Record<string, unknown>,
        [...path, index],
        usedIds,
      ))
    : [];
  const relatedFrameIds = Array.isArray(source?.related_frame_ids)
    ? source.related_frame_ids.map(String)
    : Array.isArray(source?.relatedFrameIds)
      ? source.relatedFrameIds.map(String)
      : [];

  return {
    id,
    name: String(source?.name ?? source?.label ?? "知识导图"),
    type: source?.type ? String(source.type) : undefined,
    relatedFrameIds,
    children,
  };
}
