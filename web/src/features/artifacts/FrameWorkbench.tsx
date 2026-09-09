import { useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CirclePause,
  CirclePlay,
  Code2,
  Eye,
  Gauge,
  Info,
  LoaderCircle,
  Lock,
  MousePointer2,
  Pencil,
  Save,
  Unlock,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { VisualObjectRenderer } from "@/components/workbench/visual-objects/VisualObjectRenderer";
import { cn } from "@/lib/utils";
import { lockFrame, updateFrame } from "@/services/frames";
import {
  describeFrameChanges,
  formatSnapshotValue,
  normalizeFramesArtifact,
  type ArtifactFrame,
} from "./artifact-model";
import { ParameterExperiment } from "./ParameterExperiment";

type InspectorTab = "object" | "changes" | "state" | "checks";
type InteractionMode = "browse" | "edit";

type SelectedTarget = {
  objectId: string;
  nodeId?: string;
  codeLine?: number;
};

function previousCellValues(previous: ArtifactFrame | undefined, objectId: string) {
  const object = previous?.visual_objects.find((candidate) => candidate.id === objectId);
  const cells = object?.cells ?? [];
  return Object.fromEntries(
    cells.map((cell, index) => [String(index), cell.value ?? cell.label ?? cell.text]),
  );
}

function FrameStage({
  frame,
  previous,
  interactionMode,
  showPseudocode,
  showPointers,
  selectedTarget,
  onSelectTarget,
}: {
  frame: ArtifactFrame;
  previous?: ArtifactFrame;
  interactionMode: InteractionMode;
  showPseudocode: boolean;
  showPointers: boolean;
  selectedTarget?: SelectedTarget;
  onSelectTarget: (target?: SelectedTarget) => void;
}) {
  const visibleObjects = frame.visual_objects.filter((object) => {
    if (!showPseudocode && object.type === "code_block") return false;
    if (!showPointers && object.type === "edge") return false;
    return true;
  });
  if (visibleObjects.length === 0) {
    return (
      <div className="flex min-h-80 items-center justify-center rounded-lg border border-dashed border-[var(--canvas-grid)] bg-[var(--stage-bg)] p-8 text-center">
        <div className="max-w-sm">
          <Info className="mx-auto mb-3 text-[var(--muted-foreground)]" size={24} />
          <p className="text-sm font-semibold">这一帧没有可视对象</p>
          <p className="mt-1 text-xs leading-relaxed text-[var(--muted-foreground)]">
            可继续查看旁白和状态变化；重新生成推演可补充数组、图、代码或公式等对象。
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      className="simulation-workbench-stage min-h-64 overflow-auto rounded-lg border border-[var(--canvas-grid)] bg-[var(--stage-bg)] p-4 sm:min-h-80 sm:p-6"
      onClick={(event) => {
        if (event.target === event.currentTarget) onSelectTarget(undefined);
      }}
    >
      <div className="grid min-h-[15rem] grid-cols-1 content-center gap-4 sm:min-h-[19rem] xl:grid-cols-2">
        {visibleObjects.map((object) => {
          const isStructure = object.type === "graph" || object.type === "tree";
          const isSelected = selectedTarget?.objectId === object.id;
          return (
            <div
              key={object.id}
              role="button"
              tabIndex={0}
              aria-label={`选择对象：${String(object.label ?? object.id)}`}
              aria-pressed={isSelected}
              onClick={() => onSelectTarget({ objectId: object.id })}
              onKeyDown={(event) => {
                if (event.key !== "Enter" && event.key !== " ") return;
                event.preventDefault();
                onSelectTarget({ objectId: object.id });
              }}
              className={cn(
                "simulation-workbench-object min-w-0 rounded-lg border bg-[var(--card)]/95 p-4 shadow-sm outline-none",
                isSelected
                  ? "is-selected border-[var(--interactive)]"
                  : "border-[var(--border)] hover:border-[color-mix(in_oklch,var(--interactive)_45%,var(--border))]",
                isStructure && "min-h-72 xl:col-span-2",
              )}
            >
              {(object.label || visibleObjects.length > 1) && (
                <div className="mb-3 flex items-center justify-between gap-2">
                  <p className="truncate text-xs font-semibold text-[var(--muted-foreground)]">
                    {String(object.label ?? object.id)}
                  </p>
                  <Badge variant="outline" className="font-mono text-[10px]">
                    {object.type}
                  </Badge>
                </div>
              )}
              <div className={cn("overflow-auto", isStructure && "h-60 overflow-hidden")}>
                <VisualObjectRenderer
                  object={object}
                  previousValues={previousCellValues(previous, object.id)}
                  interactionMode={interactionMode}
                  selectedNodeId={isSelected ? selectedTarget?.nodeId : undefined}
                  selectedCodeLine={isSelected ? selectedTarget?.codeLine : undefined}
                  onNodeSelect={(nodeId) => onSelectTarget({
                    objectId: object.id,
                    nodeId: nodeId || undefined,
                  })}
                  onCodeLineSelect={(codeLine) => onSelectTarget({ objectId: object.id, codeLine })}
                  className={isStructure ? "h-full w-full" : undefined}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function FrameWorkbench({
  value,
  projectId,
  onRecomputed,
  targetFrameId,
}: {
  value: unknown;
  projectId?: string;
  onRecomputed?: () => void | Promise<void>;
  targetFrameId?: string;
}) {
  const normalizedArtifact = useMemo(() => normalizeFramesArtifact(value), [value]);
  const [artifact, setArtifact] = useState(normalizedArtifact);
  const [activeIndex, setActiveIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [inspectorTab, setInspectorTab] = useState<InspectorTab>("changes");
  const [interactionMode, setInteractionMode] = useState<InteractionMode>("browse");
  const [selectedTarget, setSelectedTarget] = useState<SelectedTarget>();
  const [timelinePreview, setTimelinePreview] = useState<number>();
  const [isScrubbing, setIsScrubbing] = useState(false);
  const [reviewedFrames, setReviewedFrames] = useState<Set<string>>(() => new Set());
  const [isEditing, setIsEditing] = useState(false);
  const [draftTitle, setDraftTitle] = useState("");
  const [draftNarration, setDraftNarration] = useState("");
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "locking" | "error">("idle");
  const [saveMessage, setSaveMessage] = useState("");

  const frames = artifact.frames;
  const parameterValues = useMemo(
    () => Object.fromEntries(
      artifact.parameters.map((parameter) => [parameter.key, parameter.current_value]),
    ),
    [artifact.parameters],
  );
  const frame = frames[activeIndex];
  const previous = activeIndex > 0 ? frames[activeIndex - 1] : undefined;
  const isFirst = activeIndex === 0;
  const isLast = activeIndex === frames.length - 1;

  useEffect(() => setArtifact(normalizedArtifact), [normalizedArtifact]);

  useEffect(() => {
    const configuredSpeed = parameterValues.animation_speed;
    if (typeof configuredSpeed === "number" && Number.isFinite(configuredSpeed)) {
      setSpeed(Math.min(Math.max(configuredSpeed, 0.25), 3));
    }
  }, [parameterValues.animation_speed]);

  useEffect(() => {
    setActiveIndex(0);
    setIsPlaying(false);
    setReviewedFrames(new Set());
  }, [artifact.artifact_version, frames.length]);

  useEffect(() => {
    if (!targetFrameId) return;
    const targetIndex = frames.findIndex((candidate) => candidate.frame_id === targetFrameId);
    if (targetIndex < 0) return;
    setActiveIndex(targetIndex);
    setIsPlaying(false);
  }, [frames, targetFrameId]);

  useEffect(() => {
    if (!frame) return;
    setDraftTitle(frame.title);
    setDraftNarration(frame.narration);
    setIsEditing(false);
    setSaveStatus("idle");
    setSaveMessage("");
    setSelectedTarget(frame.visual_objects[0]?.id
      ? { objectId: frame.visual_objects[0].id }
      : undefined);
    setTimelinePreview(undefined);
  }, [frame, frame?.frame_id, frame?.narration, frame?.title]);

  useEffect(() => {
    if (!isPlaying || frames.length < 2) return;
    const timer = window.setInterval(() => {
      setActiveIndex((current) => {
        if (current >= frames.length - 1) {
          setIsPlaying(false);
          return current;
        }
        return current + 1;
      });
    }, 2200 / speed);
    return () => window.clearInterval(timer);
  }, [frames.length, isPlaying, speed]);

  if (!frame) {
    return <p className="p-6 text-sm text-[var(--muted-foreground)]">暂无可播放的推演帧</p>;
  }

  const changes = describeFrameChanges(previous, frame);
  const snapshotEntries = Object.entries(frame.state_snapshot);
  const reviewed = reviewedFrames.has(frame.frame_id);
  const selectedObject = selectedTarget
    ? frame.visual_objects.find((object) => object.id === selectedTarget.objectId)
    : undefined;

  const moveTo = (index: number) => {
    setActiveIndex(Math.min(Math.max(index, 0), frames.length - 1));
    setIsPlaying(false);
  };

  const updateCurrentFrame = (updates: Partial<ArtifactFrame>) => {
    setArtifact((current) => ({
      ...current,
      frames: current.frames.map((candidate) =>
        candidate.frame_id === frame.frame_id ? { ...candidate, ...updates } : candidate,
      ),
    }));
  };

  const saveFrame = async () => {
    if (!projectId || frame.is_locked) return;
    setSaveStatus("saving");
    setSaveMessage("");
    try {
      await updateFrame(projectId, frame.frame_id, {
        title: draftTitle.trim() || frame.title,
        narration: draftNarration,
      });
      updateCurrentFrame({ title: draftTitle.trim() || frame.title, narration: draftNarration });
      setIsEditing(false);
      setSaveStatus("idle");
      setSaveMessage("当前帧已保存");
    } catch (error) {
      setSaveStatus("error");
      setSaveMessage(error instanceof Error ? error.message : "保存失败");
    }
  };

  const toggleFrameLock = async () => {
    if (!projectId) return;
    setSaveStatus("locking");
    setSaveMessage("");
    try {
      const result = await lockFrame(projectId, frame.frame_id, !frame.is_locked);
      updateCurrentFrame({ is_locked: result.is_locked });
      setIsEditing(false);
      setSaveStatus("idle");
      setSaveMessage(result.is_locked ? "当前帧已锁定，重生成时将保留" : "当前帧已解锁");
    } catch (error) {
      setSaveStatus("error");
      setSaveMessage(error instanceof Error ? error.message : "锁定状态更新失败");
    }
  };

  return (
    <div
      className="grid min-h-0 gap-4 p-3 lg:grid-cols-[minmax(0,1fr)_19rem] lg:p-4"
      tabIndex={0}
      onKeyDown={(event) => {
        if ((event.target as HTMLElement).closest("input, textarea, select, button")) return;
        if (event.key === "ArrowLeft" && !isFirst) moveTo(activeIndex - 1);
        if (event.key === "ArrowRight" && !isLast) moveTo(activeIndex + 1);
        if (event.key === " ") {
          event.preventDefault();
          setIsPlaying((current) => !current);
        }
      }}
    >
      <div className="lg:col-span-2">
        <ParameterExperiment
          projectId={projectId}
          parameters={artifact.parameters}
          onRecomputed={onRecomputed}
        />
      </div>
      <div className="min-w-0 space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline" className="font-mono text-[10px]">{frame.frame_id}</Badge>
              {isEditing ? (
                <input
                  aria-label="帧标题"
                  value={draftTitle}
                  onChange={(event) => setDraftTitle(event.target.value)}
                  className="h-8 min-w-56 rounded-md border border-[var(--border)] bg-[var(--background)] px-2 text-sm font-bold"
                />
              ) : (
                <h3 className="text-base font-bold text-[var(--foreground)]">{frame.title}</h3>
              )}
            </div>
            {frame.learning_goal && (
              <p className="mt-1 text-xs text-[var(--muted-foreground)]">学习目标：{frame.learning_goal}</p>
            )}
          </div>
          <div className="flex items-center gap-2">
            {frame.is_locked && <Badge variant="secondary"><Lock />已锁定</Badge>}
            <Badge variant={reviewed ? "secondary" : "outline"}>
              {reviewed ? "本次已确认" : "待检查"}
            </Badge>
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2">
          <div className="flex items-center gap-1 rounded-md bg-[var(--secondary)] p-1" aria-label="画布交互模式">
            <Button
              variant={interactionMode === "browse" ? "default" : "ghost"}
              size="sm"
              aria-pressed={interactionMode === "browse"}
              onClick={() => {
                setInteractionMode("browse");
                setIsEditing(false);
              }}
            >
              <Eye />浏览
            </Button>
            <Button
              variant={interactionMode === "edit" ? "default" : "ghost"}
              size="sm"
              aria-pressed={interactionMode === "edit"}
              disabled={!projectId || frame.is_locked}
              onClick={() => setInteractionMode("edit")}
            >
              <Pencil />编辑模式
            </Button>
          </div>
          <p className="flex items-center gap-1.5 text-[11px] leading-5 text-[var(--muted-foreground)]">
            <MousePointer2 size={14} />
            {interactionMode === "browse"
              ? "拖动空白处平移 · Ctrl + 滚轮缩放 · 双击节点定位"
              : "可编辑当前帧内容；已锁定帧不会被改动"}
          </p>
        </div>

        <FrameStage
          frame={frame}
          previous={previous}
          interactionMode={interactionMode}
          showPseudocode={parameterValues.show_pseudocode !== false}
          showPointers={parameterValues.show_pointers !== false}
          selectedTarget={selectedTarget}
          onSelectTarget={(target) => {
            setSelectedTarget(target);
            if (target) setInspectorTab("object");
          }}
        />

        <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-3">
          <div className="mb-2 flex items-center justify-between gap-3 text-xs text-[var(--muted-foreground)]">
            <span>推演进度</span>
            <span className="font-mono tabular-nums">
              {timelinePreview == null ? activeIndex + 1 : `预览 ${timelinePreview + 1}`} / {frames.length}
            </span>
          </div>
          <input
            aria-label="推演帧进度"
            className="w-full accent-[var(--interactive)]"
            type="range"
            min={0}
            max={Math.max(frames.length - 1, 0)}
            value={timelinePreview ?? activeIndex}
            onPointerDown={(event) => {
              setIsScrubbing(true);
              setTimelinePreview(Number(event.currentTarget.value));
            }}
            onPointerUp={(event) => {
              const next = Number(event.currentTarget.value);
              setIsScrubbing(false);
              setTimelinePreview(undefined);
              moveTo(next);
            }}
            onBlur={() => {
              if (timelinePreview != null) moveTo(timelinePreview);
              setIsScrubbing(false);
              setTimelinePreview(undefined);
            }}
            onChange={(event) => {
              const next = Number(event.target.value);
              if (isScrubbing) setTimelinePreview(next);
              else moveTo(next);
            }}
          />
          <div className="mt-2 flex gap-1 overflow-x-auto pb-1" aria-label="推演步骤轨道">
            {frames.map((candidate, index) => (
              <button
                key={candidate.frame_id}
                type="button"
                title={`${index + 1}. ${candidate.title}`}
                aria-label={`跳转到第 ${index + 1} 帧：${candidate.title}`}
                aria-current={index === activeIndex ? "step" : undefined}
                onClick={() => moveTo(index)}
                className={cn(
                  "h-2.5 min-w-8 flex-1 rounded-full border transition-[background-color,border-color,transform] hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--interactive)]",
                  index === activeIndex
                    ? "border-[var(--interactive)] bg-[var(--interactive)]"
                    : index < activeIndex
                      ? "border-[var(--graph-settled)] bg-[var(--graph-settled)]/70"
                      : "border-[var(--border)] bg-[var(--secondary)]",
                )}
              />
            ))}
          </div>
          <div className="mt-3 flex items-center justify-between gap-2">
            <Button variant="outline" size="sm" disabled={isFirst} onClick={() => moveTo(activeIndex - 1)}>
              <ChevronLeft />上一帧
            </Button>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                aria-label="切换播放速度"
                onClick={() => setSpeed((current) => (current >= 2 ? 0.75 : current + 0.25))}
              >
                <Gauge />{speed}×
              </Button>
              <Button size="sm" onClick={() => setIsPlaying((current) => !current)} disabled={frames.length < 2}>
                {isPlaying ? <CirclePause /> : <CirclePlay />}
                {isPlaying ? "暂停" : isLast ? "重播" : "播放"}
              </Button>
            </div>
            <Button variant="outline" size="sm" disabled={isLast} onClick={() => moveTo(activeIndex + 1)}>
              下一帧<ChevronRight />
            </Button>
          </div>
        </div>
      </div>

      <aside className="min-w-0 space-y-3 lg:sticky lg:top-3 lg:self-start">
        <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="text-xs font-semibold text-[var(--muted-foreground)]">讲解旁白</p>
            {projectId && !isEditing && (
              <Button variant="ghost" size="xs" disabled={frame.is_locked} onClick={() => {
                setInteractionMode("edit");
                setIsEditing(true);
              }}>
                <Pencil />编辑
              </Button>
            )}
          </div>
          {isEditing ? (
            <div className="space-y-2">
              <textarea
                aria-label="帧旁白"
                value={draftNarration}
                onChange={(event) => setDraftNarration(event.target.value)}
                rows={6}
                className="w-full resize-y rounded-md border border-[var(--border)] bg-[var(--background)] p-2 text-sm leading-6"
              />
              <div className="flex justify-end gap-2">
                <Button variant="ghost" size="sm" onClick={() => {
                  setDraftTitle(frame.title);
                  setDraftNarration(frame.narration);
                  setIsEditing(false);
                }}>取消</Button>
                <Button size="sm" disabled={saveStatus === "saving"} onClick={saveFrame}>
                  {saveStatus === "saving" ? <LoaderCircle className="animate-spin" /> : <Save />}
                  保存帧
                </Button>
              </div>
            </div>
          ) : (
            <p className="text-sm leading-6 text-[var(--foreground)]/85">
              {frame.narration || "这一帧暂无旁白。"}
            </p>
          )}
        </section>

        <section className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--card)]">
          <div className="grid grid-cols-4 border-b border-[var(--border)] p-1">
            {([
              ["object", "对象"],
              ["changes", "变化"],
              ["state", "状态"],
              ["checks", "检查"],
            ] as const).map(([key, label]) => (
              <button
                key={key}
                aria-pressed={inspectorTab === key}
                className={cn(
                  "rounded-md px-2 py-1.5 text-xs font-medium transition-colors",
                  inspectorTab === key
                    ? "bg-[var(--secondary)] text-[var(--foreground)]"
                    : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]",
                )}
                onClick={() => setInspectorTab(key)}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="max-h-72 overflow-auto p-3">
            {inspectorTab === "object" && (
              selectedObject ? (
                <div className="space-y-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold">{String(selectedObject.label ?? selectedObject.id)}</p>
                      <p className="mt-0.5 font-mono text-[10px] text-[var(--muted-foreground)]">{selectedObject.id}</p>
                    </div>
                    <Badge variant="outline" className="font-mono text-[10px]">{selectedObject.type}</Badge>
                  </div>
                  {selectedTarget?.nodeId && (
                    <p className="rounded-md bg-[var(--secondary)] px-2.5 py-2 text-xs">
                      当前节点：<span className="font-mono font-semibold">{selectedTarget.nodeId}</span>
                    </p>
                  )}
                  {selectedTarget?.codeLine && (
                    <p className="flex items-center gap-2 rounded-md bg-[var(--secondary)] px-2.5 py-2 text-xs">
                      <Code2 size={14} className="text-[var(--interactive)]" />
                      已定位代码第 {selectedTarget.codeLine} 行
                    </p>
                  )}
                  {!selectedTarget?.nodeId && !selectedTarget?.codeLine && (
                    <p className="text-xs leading-5 text-[var(--muted-foreground)]">
                      {selectedObject.type === "code_block"
                        ? "点击代码行可单独定位，并保留当前行的视觉焦点。"
                        : selectedObject.type === "graph" || selectedObject.type === "tree"
                          ? "单击节点查看对象，双击可将它居中放大。"
                          : "当前对象已选中，可结合变化和状态面板查看本帧更新。"}
                    </p>
                  )}
                </div>
              ) : (
                <p className="text-xs text-[var(--muted-foreground)]">点击画布中的对象查看详情</p>
              )
            )}
            {inspectorTab === "changes" && (
              changes.length > 0 ? (
                <ul className="space-y-2">
                  {changes.map((change) => (
                    <li key={change} className="rounded-md bg-[var(--secondary)]/65 px-2.5 py-2 text-xs leading-5">
                      {change}
                    </li>
                  ))}
                </ul>
              ) : <p className="text-xs text-[var(--muted-foreground)]">与上一帧相比无结构化变化</p>
            )}
            {inspectorTab === "state" && (
              snapshotEntries.length > 0 ? (
                <dl className="space-y-2">
                  {snapshotEntries.map(([key, value]) => (
                    <div key={key} className="border-b border-[var(--border)] pb-2 last:border-0">
                      <dt className="font-mono text-[10px] text-[var(--muted-foreground)]">{key}</dt>
                      <dd className="mt-1 break-all text-xs leading-5">{formatSnapshotValue(value)}</dd>
                    </div>
                  ))}
                </dl>
              ) : <p className="text-xs text-[var(--muted-foreground)]">这一帧没有状态快照</p>
            )}
            {inspectorTab === "checks" && (
              frame.checks.length > 0 ? (
                <ul className="space-y-2">
                  {frame.checks.map((check, index) => (
                    <li key={`${check.type ?? "check"}-${index}`} className="flex gap-2 text-xs leading-5">
                      <CheckCircle2 className="mt-0.5 shrink-0 text-[var(--success)]" size={14} />
                      {String(check.message ?? check.type ?? "检查项")}
                    </li>
                  ))}
                </ul>
              ) : <p className="text-xs text-[var(--muted-foreground)]">暂无自动检查项</p>
            )}
          </div>
        </section>

        <Button
          variant={reviewed ? "secondary" : "outline"}
          className="w-full"
          onClick={() => setReviewedFrames((current) => {
            const next = new Set(current);
            if (next.has(frame.frame_id)) next.delete(frame.frame_id);
            else next.add(frame.frame_id);
            return next;
          })}
        >
          <CheckCircle2 />{reviewed ? "取消本次确认" : "确认当前帧"}
        </Button>
        {projectId && (
          <Button
            variant="outline"
            className="w-full"
            disabled={saveStatus === "locking"}
            onClick={toggleFrameLock}
          >
            {saveStatus === "locking" ? <LoaderCircle className="animate-spin" /> : frame.is_locked ? <Unlock /> : <Lock />}
            {frame.is_locked ? "解锁当前帧" : "锁定并保留当前帧"}
          </Button>
        )}
        {saveMessage && (
          <p className={`px-1 text-[10px] leading-4 ${saveStatus === "error" ? "text-[var(--error)]" : "text-[var(--muted-foreground)]"}`} role="status">
            {saveMessage}
          </p>
        )}
        <p className="px-1 text-[10px] leading-4 text-[var(--muted-foreground)]">
          确认状态仅用于当前检查会话，不会写回项目数据。
        </p>
      </aside>
    </div>
  );
}
