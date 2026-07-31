/**
 * ModuleResultsPanel — 模块成果聚合展示面板。
 *
 * 读取 module_outputs，按模块分类渲染对应的展示组件。
 * 对齐 DESIGN.md：纸本质感、语义色、编辑式排版、章节编号。
 */

import { Brain, Layers, PenTool, Play, Video, GitCompare, AlertTriangle, Map, Code2 } from "lucide-react";
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
import { KnowledgeCard } from "@/components/workbench/KnowledgeCard";
import { MindmapView } from "@/components/workbench/MindmapView";
import type { ProjectDetailResponse } from "@/services/projects";
import { useState, useCallback } from "react";
import { RefreshCw, Pencil } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { regenerateModule } from "@/services/generate";
import type { SSEModuleDoneEvent, SSEModuleErrorEvent } from "@/services/sse";

// ============================================================================
// 模块配置
// ============================================================================

const SECTION_CONFIG: Record<string, { title: string; icon: typeof Brain; order: number }> = {
  mindmap:   { title: "思维导图",   icon: Brain,          order: 1 },
  cards:     { title: "知识卡片",   icon: Layers,         order: 2 },
  frames:    { title: "交互推演",   icon: Play,           order: 3 },
  quiz:      { title: "小练习",     icon: PenTool,        order: 4 },
  comparison:{ title: "算法对比",   icon: GitCompare,     order: 5 },
  misconception: { title: "常见误区", icon: AlertTriangle, order: 6 },
  pathway:   { title: "学习路径",   icon: Map,            order: 7 },
  sandbox:   { title: "代码沙箱",   icon: Code2,          order: 8 },
  video:     { title: "教学视频",   icon: Video,          order: 9 },
};

export interface ModuleResultsPanelProps {
  project: ProjectDetailResponse | null;
  onNavigateTab?: (tab: string) => void;
}

export function ModuleResultsPanel({ project, onNavigateTab }: ModuleResultsPanelProps) {
  const moduleOutputs = (project?.module_outputs ?? {}) as Record<string, unknown>;
  const [localOutputs, setLocalOutputs] = useState<Record<string, unknown>>(moduleOutputs);
  const [isRegenerating, setIsRegenerating] = useState<Record<string, boolean>>({});
  const [showEditor, setShowEditor] = useState(false);

  const displayedOutputs = { ...moduleOutputs, ...localOutputs };
  const entries = Object.entries(displayedOutputs).filter(([, v]) => v != null);

  const handleRegenerate = useCallback((moduleId: string) => {
    if (!project?.id || isRegenerating[moduleId]) return;
    setIsRegenerating((p) => ({ ...p, [moduleId]: true }));

    regenerateModule(project.id, moduleId, {
      onModuleDone: (event: SSEModuleDoneEvent) => {
        setLocalOutputs((prev) => ({ ...prev, [event.module_id]: event.output }));
        setIsRegenerating((p) => ({ ...p, [moduleId]: false }));
      },
      onModuleError: (event: SSEModuleErrorEvent) => {
        setIsRegenerating((p) => ({ ...p, [moduleId]: false }));
      },
    });
  }, [project?.id, isRegenerating]);

  if (entries.length === 0) {
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

  // 按 order 排序
  const sorted = entries
    .map(([key, value]) => ({ key, value, config: SECTION_CONFIG[key] }))
    .filter((e) => e.config)
    .sort((a, b) => a.config.order - b.config.order);

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div className="mb-2">
        <h2 className="text-lg font-bold text-[var(--foreground)]">教学成果</h2>
        <p className="text-sm text-[var(--muted-foreground)]">
          已生成 {sorted.length} 个模块产物
        </p>
      </div>

      {sorted.map(({ key, value, config }) => {
        const SectionIcon = config.icon;
        return (
          <section
            key={key}
            className="rounded-xl border border-[var(--border)] bg-[var(--card)] overflow-hidden"
          >
            {/* 节标题 */}
            <div className="flex items-center gap-3 border-b border-[var(--border)] px-6 py-3">
              <span className="font-mono text-xs text-[var(--muted-foreground)] tabular-nums">
                {String(config.order).padStart(2, "0")}
              </span>
              <SectionIcon size={16} className="text-[var(--interactive)]" />
              <span className="text-sm font-semibold text-[var(--foreground)]">{config.title}</span>
              <div className="ml-auto flex items-center gap-2">
                {/* 重新生成按钮 + 并发锁 */}
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 gap-1 text-xs"
                  disabled={isRegenerating[key]}
                  onClick={() => handleRegenerate(key)}
                >
                  <RefreshCw size={12} className={isRegenerating[key] ? "animate-spin" : ""} />
                  {isRegenerating[key] ? "生成中" : "重生成"}
                </Button>
                {/* frames: 打开编辑器 */}
                {key === "frames" && (
                  <Button variant="ghost" size="sm" className="h-6 gap-1 text-xs" onClick={() => setShowEditor(true)}>
                    <Pencil size={12} /> 编辑
                  </Button>
                )}
              </div>
              <Badge variant="outline" className="text-xs text-[var(--muted-foreground)]">
                已生成
              </Badge>
            </div>
            {/* 内容 */}
            <div>
              {renderModuleContent(key, value, onNavigateTab)}
            </div>
          </section>
        );
      })}
    </div>
  );
}

function renderModuleContent(
  moduleId: string,
  value: unknown,
  onNavigateTab?: (tab: string) => void,
): React.ReactNode {
  switch (moduleId) {
    case "mindmap":
      return <MindmapView root={(value as { root?: Record<string, unknown> })?.root} />;
    case "cards":
      return (
        <div className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-3">
          {((value as { cards?: Array<Record<string, unknown>> })?.cards ?? []).map(
            (card, i) => (
              <KnowledgeCard key={card.id as string ?? i} card={{
                id: card.id as string,
                title: card.title as string,
                definition: card.definition as string,
                intuition: card.intuition as string,
                pitfalls: (card.pitfalls as string[]) ?? [],
                formula: card.formula as string | null,
                pseudocode: card.pseudocode as string | null,
                relatedFrameIds: card.related_frame_ids as string[],
                category: card.category as string,
                difficulty: card.difficulty as number,
              }} />
            )
          )}
        </div>
      );
    case "quiz":
      return <QuizPanel questions={(value as { questions?: QuizQuestion[] })?.questions ?? []} />;
    case "frames": {
      const dsl = value as Record<string, unknown>;
      const frames = (dsl?.frames ?? []) as Array<Record<string, unknown>>;
      const frameCount = frames.length;
      return (
        <div className="p-4 space-y-3">
          <p className="text-sm text-[var(--muted-foreground)]">
            推演帧已生成，共 {frameCount} 帧
          </p>
          {frames.length > 0 && (
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {frames.map((f, i) => {
                const vos = (f?.visual_objects ?? []) as Array<Record<string, unknown>>;
                const voTypes = [...new Set(vos.map((v) => String(v?.type ?? ""))).values()].filter(Boolean);
                return (
                  <div key={String(f?.frame_id ?? i)} className="rounded-lg border border-[var(--border)] p-3">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs text-[var(--muted-foreground)] tabular-nums">
                        {String(f?.frame_id ?? `f_${i + 1}`)}
                      </span>
                      <span className="text-sm font-medium text-[var(--foreground)]">
                        {String(f?.title ?? "")}
                      </span>
                      {f?.learning_goal && (
                        <span className="text-xs text-[var(--muted-foreground)]">
                          — {String(f.learning_goal)}
                        </span>
                      )}
                    </div>
                    {f?.narration && (
                      <p className="mt-1 text-xs leading-relaxed text-[var(--foreground)]/80">
                        {String(f.narration)}
                      </p>
                    )}
                    {voTypes.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {voTypes.map((t) => (
                          <span key={t} className="inline-block rounded border border-[var(--border)] px-1.5 py-0.5 text-[10px] text-[var(--muted-foreground)]">
                            {t}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      );
    }
    case "video":
      return (
        <div className="p-4 text-sm text-[var(--muted-foreground)]">
          视频导出任务：{(value as Record<string, unknown>)?.status as string ?? "未知"}
          {(value as Record<string, unknown>)?.job_id && (
            <span className="ml-2 font-mono text-xs">
              {(value as Record<string, unknown>).job_id as string}
            </span>
          )}
          {onNavigateTab && (
            <Button variant="link" size="sm" className="ml-3" onClick={() => onNavigateTab("export")}>
              前往导出
            </Button>
          )}
        </div>
      );
    case "comparison":
      return <ComparisonView data={value as ComparisonData} />;
    case "misconception":
      return <MisconceptionGallery items={(value as { items?: MisconceptionItem[] })?.items ?? []} />;
    case "pathway":
      return <LearningPathway data={value as PathwayData} />;
    case "sandbox":
      return <CodeSandbox data={value as SandboxData} />;
    default:
      return (
        <div className="p-4 text-sm text-[var(--muted-foreground)]">
          <pre className="max-h-32 overflow-auto text-xs">{JSON.stringify(value, null, 2)}</pre>
        </div>
      );
  }
}
