import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  BotIcon,
  CheckCircle2Icon,
  PauseIcon,
  PlayIcon,
  RotateCcwIcon,
  SkipBackIcon,
  SkipForwardIcon,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ButtonGroup } from "@/components/ui/button-group";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import type { GenerationState } from "./AiStatusStrip";
import { SimulationGraph } from "./SimulationGraph";
import {
  getDistanceLabel,
  graphNodeIds,
  simulationFrames,
  PlayState,
  canTransition,
} from "./simulation-model";

type SimulationPreviewProps = {
  frame: number;
  generation: GenerationState;
  onFrameChange: (frame: number) => void;
  onRegenerate: () => void;
};

/** 播放速度选项（毫秒/帧） */
const SPEED_OPTIONS: { label: string; value: number }[] = [
  { label: "0.5×", value: 2800 },
  { label: "1×", value: 1400 },
  { label: "1.5×", value: 930 },
  { label: "2×", value: 700 },
];

export function SimulationPreview({
  frame,
  generation,
  onFrameChange,
  onRegenerate,
}: SimulationPreviewProps) {
  // ── 播放状态机 ─────────────────────────────────────────
  const [playState, setPlayState] = useState<PlayState>(PlayState.IDLE);
  const [playSpeed, setPlaySpeed] = useState(1); // speedOptions 索引
  const speedMs = SPEED_OPTIONS[playSpeed]?.value ?? 1400;
  const totalFrames = simulationFrames.length;

  // 是否需要等待交互（当前帧有 interactionHooks）
  const needsInteraction = useMemo(() => {
    const current = simulationFrames[Math.min(totalFrames - 1, Math.max(0, frame - 1))];
    return (current?.interactionHooks?.length ?? 0) > 0;
  }, [frame, totalFrames]);

  // ── 状态转换 ──────────────────────────────────────────
  const transitionTo = useCallback(
    (next: PlayState) => {
      if (canTransition(playState, next)) {
        setPlayState(next);
      }
    },
    [playState],
  );

  const handlePlay = useCallback(() => {
    if (playState === PlayState.IDLE || playState === PlayState.PAUSE) {
      transitionTo(PlayState.PLAYING);
    }
  }, [playState, transitionTo]);

  const handlePause = useCallback(() => {
    if (playState === PlayState.PLAYING) {
      transitionTo(PlayState.PAUSE);
    }
  }, [playState, transitionTo]);

  const handleReset = useCallback(() => {
    onFrameChange(1);
    setPlayState(PlayState.IDLE);
  }, [onFrameChange]);

  const handleTogglePlay = useCallback(() => {
    if (playState === PlayState.PLAYING) {
      handlePause();
    } else {
      handlePlay();
    }
  }, [playState, handlePlay, handlePause]);

  // ── 自动播放循环 ──────────────────────────────────────
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    if (playState !== PlayState.PLAYING) {
      if (timerRef.current !== null) {
        window.clearInterval(timerRef.current);
        timerRef.current = null;
      }
      return;
    }

    timerRef.current = window.setInterval(() => {
      if (frame >= totalFrames) {
        // 播放完毕 → 回到 IDLE
        setPlayState(PlayState.IDLE);
        return;
      }

      // 检查下一帧是否需要交互
      const nextFrame = simulationFrames[frame]; // frame 是 1-indexed
      if (nextFrame?.interactionHooks?.length) {
        onFrameChange(frame + 1);
        setPlayState(PlayState.WAITING);
        return;
      }

      onFrameChange(frame + 1);
    }, speedMs);

    return () => {
      if (timerRef.current !== null) {
        window.clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [playState, frame, totalFrames, speedMs, onFrameChange]);

  // ── 键盘快捷键 ────────────────────────────────────────
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      switch (e.key) {
        case " ":
          e.preventDefault();
          handleTogglePlay();
          break;
        case "ArrowLeft":
          e.preventDefault();
          if (frame > 1) onFrameChange(frame - 1);
          break;
        case "ArrowRight":
          e.preventDefault();
          if (frame < totalFrames) onFrameChange(frame + 1);
          break;
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [frame, totalFrames, handleTogglePlay, onFrameChange]);

  const currentFrame = simulationFrames[Math.min(simulationFrames.length - 1, Math.max(0, frame - 1))];

  const distanceRows = useMemo(
    () =>
      graphNodeIds.map((node) => ({
        node,
        distance: getDistanceLabel(currentFrame.distances[node]),
        previous: currentFrame.predecessors[node] ?? "—",
        status:
          currentFrame.currentNode === node
            ? "当前节点"
            : currentFrame.settledNodes.includes(node)
              ? "已确定"
              : "未访问",
      })),
    [currentFrame],
  );

  const relaxationCount = useMemo(
    () =>
      simulationFrames
        .slice(0, frame)
        .reduce((count, item) => count + item.changedEdges.length, 0),
    [frame],
  );

  const settledLabel = currentFrame.settledNodes.length
    ? `{ ${currentFrame.settledNodes.join(", ")} }`
    : "∅";

  return (
    <section
      aria-labelledby="simulation-heading"
      className="grid min-h-0 min-w-0 overflow-hidden rounded-xl border bg-card shadow-[0_1px_3px_color-mix(in_oklch,var(--foreground)_5%,transparent)] lg:h-full lg:grid-cols-[minmax(0,1fr)_18rem]"
    >
      <div className="flex min-h-[38rem] min-w-0 flex-col lg:min-h-0">
        <header className="flex min-h-12 shrink-0 flex-wrap items-center justify-between gap-3 border-b px-4 py-2.5">
          <div className="flex items-center gap-3">
            <div>
              <h2 id="simulation-heading" className="text-[15px] font-semibold tracking-[-0.01em]">互动推演</h2>
              <p className="text-xs text-muted-foreground">逐帧观察选点、松弛与距离变化</p>
            </div>
            <Badge variant="outline" className="font-normal">源点 A</Badge>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span
              className={cn(
                "size-2 rounded-full",
                playState === PlayState.PLAYING && "bg-success animate-pulse",
                playState === PlayState.PAUSE && "bg-warning",
                playState === PlayState.WAITING && "bg-info animate-pulse",
                playState === PlayState.IDLE && "bg-muted-foreground",
                playState === PlayState.RECOMPUTE && "bg-info animate-spin",
              )}
              aria-hidden="true"
            />
            {playState === PlayState.PLAYING && "播放中"}
            {playState === PlayState.PAUSE && "已暂停"}
            {playState === PlayState.WAITING && "等待交互"}
            {playState === PlayState.IDLE && "就绪"}
            {playState === PlayState.RECOMPUTE && "重算中"}
          </div>
        </header>

        <div className="flex min-h-0 flex-1 flex-col gap-2.5 p-2.5 sm:gap-3 sm:p-3">
          <figure className="relative min-h-[22rem] flex-1 overflow-hidden rounded-lg border border-primary/35 bg-[var(--stage-bg)] sm:min-h-[26rem] lg:min-h-0">
            <figcaption className="sr-only">
              Dijkstra 六节点交互图，当前节点为 {currentFrame.currentNode}
            </figcaption>
            <SimulationGraph frame={currentFrame} />
            <div className="pointer-events-none absolute top-3 left-3 rounded-md border border-success/30 bg-card/88 px-2.5 py-1 text-xs font-medium text-success backdrop-blur">
              源点 A
            </div>
            <div className="pointer-events-none absolute top-3 right-3 hidden items-center gap-3 rounded-md border bg-card/88 px-2.5 py-1.5 text-[11px] text-muted-foreground shadow-sm backdrop-blur sm:flex">
              <span className="flex items-center gap-1.5"><span className="size-2 rounded-full bg-primary" />当前节点</span>
              <span className="flex items-center gap-1.5"><span className="size-2 rounded-full bg-success" />已确定</span>
              <span className="flex items-center gap-1.5"><span className="h-0 w-4 border-t-2 border-dashed border-primary" />本帧更新</span>
            </div>
          </figure>

          <div className="flex shrink-0 items-start gap-3 rounded-lg border bg-muted/35 px-3 py-2 text-sm">
            <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
              <BotIcon className="size-4" aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <p className="font-medium text-primary">AI 讲解</p>
                <Badge variant="secondary" className="font-normal">{currentFrame.title}</Badge>
              </div>
              <p className="mt-0.5 leading-5 text-muted-foreground sm:leading-6">
                {currentFrame.narration}
              </p>
            </div>
          </div>

          <div className="flex shrink-0 flex-wrap items-center gap-2 px-1 sm:gap-3">
            <div className="mr-2 text-sm font-medium">
              步骤 <span className="text-primary tabular-nums">{frame}</span>{" "}
              <span className="text-muted-foreground">/ {totalFrames}</span>
            </div>
            <ButtonGroup aria-label="演示播放控制">
              <Button variant="outline" onClick={() => onFrameChange(Math.max(1, frame - 1))} disabled={frame === 1}>
                <SkipBackIcon data-icon="inline-start" />上一帧
              </Button>
              <Button
                onClick={handleTogglePlay}
                aria-label={
                  playState === PlayState.PLAYING ? "暂停演示" :
                  playState === PlayState.WAITING ? "等待交互中" :
                  "播放演示"
                }
                disabled={playState === PlayState.WAITING || playState === PlayState.RECOMPUTE}
              >
                {playState === PlayState.PLAYING ? (
                  <><PauseIcon data-icon="inline-start" />暂停</>
                ) : playState === PlayState.WAITING ? (
                  <><BotIcon data-icon="inline-start" className="animate-pulse" />交互中</>
                ) : playState === PlayState.RECOMPUTE ? (
                  <><BotIcon data-icon="inline-start" className="animate-spin" />重算中</>
                ) : (
                  <><PlayIcon data-icon="inline-start" />播放</>
                )}
              </Button>
              <Button variant="outline" onClick={() => onFrameChange(Math.min(totalFrames, frame + 1))} disabled={frame === totalFrames}>
                下一帧<SkipForwardIcon data-icon="inline-end" />
              </Button>
            </ButtonGroup>
            <div className="ml-auto flex items-center gap-2 max-sm:w-full max-sm:justify-end">
              <Button variant="ghost" size="sm" onClick={handleReset}>
                <RotateCcwIcon data-icon="inline-start" />重置
              </Button>
              <div className="flex items-center gap-1.5">
                {SPEED_OPTIONS.map((opt, idx) => (
                  <Button
                    key={opt.label}
                    variant={playSpeed === idx ? "default" : "outline"}
                    size="sm"
                    className="h-7 px-2 text-xs"
                    onClick={() => setPlaySpeed(idx)}
                  >
                    {opt.label}
                  </Button>
                ))}
              </div>
            </div>
          </div>

          <ol className="grid shrink-0 grid-cols-7 items-center gap-1 px-1 sm:[grid-template-columns:repeat(14,minmax(0,1fr))]" aria-label="推演时间轴">
            {simulationFrames.map((item) => (
              <li key={item.id} className="flex min-w-0 flex-col items-center gap-1">
                <button
                  type="button"
                  title={item.title}
                  aria-label={`跳到第 ${item.id} 帧`}
                  aria-current={item.id === frame ? "step" : undefined}
                  onClick={() => onFrameChange(item.id)}
                  className={cn(
                    "size-3 rounded-full border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                    item.id < frame && "border-primary bg-primary",
                    item.id === frame && "size-5 border-primary bg-primary text-[9px] text-primary-foreground",
                    item.id > frame && "border-border bg-muted",
                  )}
                >
                  {item.id === frame ? item.id : <span className="sr-only">第 {item.id} 帧</span>}
                </button>
                <span className={cn("text-[10px] tabular-nums text-muted-foreground", item.id === frame && "font-medium text-primary")}>{item.id}</span>
              </li>
            ))}
          </ol>
        </div>
      </div>

      <aside aria-label="推演检查器" className="min-h-[26rem] min-w-0 overflow-hidden border-t bg-card lg:min-h-0 lg:border-t-0 lg:border-l">
        <Tabs defaultValue="state" className="h-full min-h-0 flex-col gap-0">
          <TabsList variant="line" className="h-12 w-full! justify-stretch border-b px-3">
            <TabsTrigger value="lecture">讲解</TabsTrigger>
            <TabsTrigger value="state">状态</TabsTrigger>
            <TabsTrigger value="params">参数</TabsTrigger>
          </TabsList>

          <TabsContent value="lecture" className="min-h-0 w-full flex-1 overflow-y-auto p-4">
            <h3 className="font-semibold">{currentFrame.title}</h3>
            <p className="mt-3 text-sm leading-6 text-muted-foreground">{currentFrame.narration}</p>
            <Button className="mt-4 w-full" variant="outline" onClick={onRegenerate}>优化本帧讲解</Button>
          </TabsContent>

          <TabsContent value="state" className="min-h-0 w-full flex-1 overflow-y-auto p-4">
            <div className="flex items-center justify-between gap-3">
              <h3 className="font-semibold">当前节点 {currentFrame.currentNode}</h3>
              <Badge variant="secondary">步骤 {frame} / {totalFrames}</Badge>
            </div>
            <dl className="mt-4 grid grid-cols-[1fr_auto] gap-x-3 gap-y-3 text-sm">
              <dt className="text-muted-foreground">当前阶段</dt><dd>{currentFrame.title}</dd>
              <dt className="text-muted-foreground">确定距离</dt><dd className="tabular-nums">{getDistanceLabel(currentFrame.distances[currentFrame.currentNode])}</dd>
              <dt className="text-muted-foreground">已确定集合</dt><dd>{settledLabel}</dd>
            </dl>
            <div className="my-5 border-t" />
            <h3 className="mb-3 text-sm font-semibold">距离表</h3>
            <div className="overflow-hidden rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>节点</TableHead><TableHead>距离</TableHead><TableHead>前驱</TableHead><TableHead><span className="sr-only">状态</span></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {distanceRows.map((row) => (
                    <TableRow key={row.node} data-state={row.status === "当前节点" ? "selected" : undefined}>
                      <TableCell className="font-medium">{row.node}</TableCell>
                      <TableCell className="tabular-nums">{row.distance}</TableCell>
                      <TableCell>{row.previous}</TableCell>
                      <TableCell>
                        <span className="sr-only">{row.status}</span>
                        {row.status === "已确定" ? (
                          <CheckCircle2Icon className="size-3.5 text-success" aria-hidden="true" />
                        ) : (
                          <span className={cn("block size-2.5 rounded-full border", row.status === "当前节点" ? "border-primary bg-primary ring-2 ring-primary/20" : "border-muted-foreground/45")} aria-hidden="true" />
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            <div className="my-5 border-t" />
            <h3 className="mb-3 text-sm font-semibold">算法状态</h3>
            <dl className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-3 text-sm">
              <dt className="text-muted-foreground">源点</dt><dd>A</dd>
              <dt className="text-muted-foreground">已确定节点</dt><dd>{currentFrame.settledNodes.length} / {graphNodeIds.length}</dd>
              <dt className="text-muted-foreground">剩余节点</dt><dd>{graphNodeIds.length - currentFrame.settledNodes.length}</dd>
              <dt className="text-muted-foreground">有效松弛</dt><dd>{relaxationCount}</dd>
            </dl>
          </TabsContent>

          <TabsContent value="params" className="min-h-0 w-full flex-1 overflow-y-auto p-4">
            <h3 className="font-semibold">推演参数</h3>
            <label className="mt-4 block text-sm font-medium" htmlFor="source-node">源点</label>
            <select id="source-node" className="mt-2 h-9 w-full rounded-lg border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring" defaultValue="A">
              <option>A</option><option>B</option><option>C</option>
            </select>

            <div className="mt-5">
              <label className="block text-sm font-medium mb-2">播放速度</label>
              <Slider
                value={[playSpeed]}
                min={0}
                max={SPEED_OPTIONS.length - 1}
                step={1}
                onValueChange={([v]) => v != null && setPlaySpeed(v)}
                aria-label="播放速度调节"
              />
              <p className="mt-1.5 text-xs text-muted-foreground">
                当前: {SPEED_OPTIONS[playSpeed]?.label ?? "1×"}
              </p>
            </div>

            <div className="mt-5 flex items-center justify-between gap-3">
              <label htmlFor="show-weights" className="text-sm font-medium">显示边权重</label>
              <Switch id="show-weights" defaultChecked />
            </div>
            <div className="mt-5 flex items-center justify-between gap-3">
              <label htmlFor="auto-narration" className="text-sm font-medium">自动讲解</label>
              <Switch id="auto-narration" defaultChecked />
            </div>
            <Button className="mt-6 w-full" disabled={generation === "planning"} onClick={onRegenerate}>应用并重新生成</Button>
          </TabsContent>
        </Tabs>
      </aside>
    </section>
  );
}
