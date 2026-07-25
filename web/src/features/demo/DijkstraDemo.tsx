import { useEffect, useMemo, useRef } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ChevronLeft, ChevronRight, Pause, Play, RotateCcw, SkipForward } from "lucide-react";
import { SimulationGraph } from "@/components/workbench/SimulationGraph";
import { buildDijkstraScenario } from "@/components/workbench/simulation-model";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { DemoParameterPanel } from "./DemoParameterPanel";
import { DemoStatusTable } from "./DemoStatusTable";
import { DemoTimeline } from "./DemoTimeline";
import { useDemoPlayback } from "./useDemoPlayback";

const modeLabels = {
  poster: "准备体验",
  autoplay: "自动演示",
  paused: "演示已暂停",
  explore: "自由体验",
  completed: "演示完成",
} as const;

const staticCheckpoints = [
  { label: "起点设置", frameIndex: 0 },
  { label: "初始化距离", frameIndex: 1 },
  { label: "首轮松弛", frameIndex: 3 },
  { label: "路径收敛", frameIndex: 7 },
  { label: "完成结果", frameIndex: 13 },
] as const;

type DijkstraDemoProps = {
  compact?: boolean;
};

function shouldPreserveNativeKeyboardControl(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) return false;

  return target.isContentEditable
    || target.closest("input, textarea, select, button, a, [contenteditable]") !== null;
}

export function DijkstraDemo({ compact = false }: DijkstraDemoProps) {
  const initialScenario = useMemo(() => buildDijkstraScenario(), []);
  const {
    state,
    prefersReducedMotion,
    play,
    pause,
    replay,
    skip,
    goToFrame,
    setEdgeWeight,
    setSpeed,
  } = useDemoPlayback(initialScenario.frames.length);
  const scenario = useMemo(
    () => buildDijkstraScenario({ edgeOverrides: { "B-D": state.edgeWeight } }),
    [state.edgeWeight],
  );
  const frame = scenario.frames[Math.min(state.frameIndex, scenario.frames.length - 1)];
  const demoRef = useRef<HTMLElement>(null);
  const primaryPlaybackControl =
    prefersReducedMotion
      ? null
      : state.mode === "autoplay"
      ? { label: "暂停演示", onClick: pause, icon: <Pause data-icon="inline-start" /> }
      : state.mode === "paused"
        ? { label: "继续演示", onClick: play, icon: <Play data-icon="inline-start" /> }
        : state.mode === "poster"
          ? { label: "观看交互演示", onClick: play, icon: <Play data-icon="inline-start" /> }
          : null;

  useEffect(() => {
    const demoRoot = demoRef.current;
    if (!demoRoot || typeof IntersectionObserver === "undefined") return;

    const observer = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting && state.mode === "autoplay") pause();
    });
    observer.observe(demoRoot);
    return () => observer.disconnect();
  }, [pause, state.mode]);

  useEffect(() => {
    const handlePlaybackKeyboard = (event: KeyboardEvent) => {
      if (
        event.defaultPrevented
        || event.altKey
        || event.ctrlKey
        || event.metaKey
        || event.shiftKey
        || event.repeat
        || shouldPreserveNativeKeyboardControl(event.target)
      ) {
        return;
      }

      if (event.key === " " || event.code === "Space") {
        if (prefersReducedMotion) return;

        if (state.mode === "autoplay") {
          event.preventDefault();
          pause();
        } else if (state.mode === "poster" || state.mode === "paused") {
          event.preventDefault();
          play();
        } else if (state.mode === "completed") {
          event.preventDefault();
          replay();
        }
        return;
      }

      if (event.key === "ArrowRight") {
        event.preventDefault();
        const nextFrame = Math.min(state.frameIndex + 1, scenario.frames.length - 1);
        if (nextFrame !== state.frameIndex) goToFrame(nextFrame);
      } else if (event.key === "ArrowLeft") {
        event.preventDefault();
        const previousFrame = Math.max(state.frameIndex - 1, 0);
        if (previousFrame !== state.frameIndex) goToFrame(previousFrame);
      }
    };

    document.addEventListener("keydown", handlePlaybackKeyboard);
    return () => document.removeEventListener("keydown", handlePlaybackKeyboard);
  }, [goToFrame, pause, play, prefersReducedMotion, replay, scenario.frames.length, state.frameIndex, state.mode]);

  return (
    <section ref={demoRef} className={cn("dijkstra-demo", compact && "dijkstra-demo--compact")} aria-label="Dijkstra 最短路径互动演示">
      <header className="dijkstra-demo__header">
        <div>
          <p className="demo-eyebrow">交互案例 · Dijkstra 最短路径</p>
          <h2>从 A 出发，逐步确定最短距离</h2>
        </div>
        <p className="dijkstra-demo__mode" role="status">{modeLabels[state.mode]}</p>
      </header>

      <div className="dijkstra-demo__stage">
        <div className="dijkstra-demo__graph stage-grid paper-surface">
          <SimulationGraph
            frame={frame}
            edges={scenario.edges}
            compact={compact || undefined}
            panActivationKeyCode={prefersReducedMotion ? null : undefined}
          />
        </div>
        <DemoStatusTable frame={frame} />
        {!compact && (
          <DemoParameterPanel
            edgeWeight={state.edgeWeight}
            speed={state.speed}
            onEdgeWeightChange={setEdgeWeight}
            onSpeedChange={setSpeed}
          />
        )}
      </div>

      <div className="dijkstra-demo__explanation">
        <div className="dijkstra-demo__narration" aria-live="polite">
          <p className="demo-eyebrow">{frame.title}</p>
          <AnimatePresence mode="wait" initial={false}>
            <motion.p
              key={`${state.edgeWeight}-${frame.id}`}
              className="dijkstra-demo__narration-copy"
              initial={prefersReducedMotion ? false : { opacity: 0, y: 5 }}
              animate={{ opacity: 1, y: 0 }}
              exit={prefersReducedMotion ? undefined : { opacity: 0, y: -3 }}
              transition={{ duration: 0.18 }}
            >
              {frame.narration}
            </motion.p>
          </AnimatePresence>
          {state.edgeWeight === 3 && <p role="status" className="dijkstra-demo__result">D 的最短距离变为 5</p>}
        </div>
        <div className="dijkstra-demo__controls" aria-label="演示播放控制">
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="dijkstra-demo__frame-control"
            aria-label="上一帧"
            title="上一帧"
            disabled={state.frameIndex === 0}
            onClick={() => goToFrame(state.frameIndex - 1)}
          >
            <ChevronLeft aria-hidden="true" />
          </Button>
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="dijkstra-demo__frame-control"
            aria-label="下一帧"
            title="下一帧"
            disabled={state.frameIndex === scenario.frames.length - 1}
            onClick={() => goToFrame(state.frameIndex + 1)}
          >
            <ChevronRight aria-hidden="true" />
          </Button>
          {prefersReducedMotion ? (
            <div className="dijkstra-demo__checkpoints" role="group" aria-label="静态演示检查点">
              {staticCheckpoints.map((checkpoint) => (
                <Button
                  key={checkpoint.label}
                  type="button"
                  variant="outline"
                  size="sm"
                  aria-pressed={state.frameIndex === checkpoint.frameIndex}
                  onClick={() => goToFrame(checkpoint.frameIndex)}
                >
                  {checkpoint.label}
                </Button>
              ))}
            </div>
          ) : (
            <>
              {primaryPlaybackControl && (
                <Button type="button" onClick={primaryPlaybackControl.onClick}>
                  {primaryPlaybackControl.icon}{primaryPlaybackControl.label}
                </Button>
              )}
              {state.mode !== "poster" && (
                <Button type="button" variant="outline" onClick={skip}>
                  <SkipForward data-icon="inline-start" />跳过演示
                </Button>
              )}
              {state.mode !== "autoplay" && (
                <Button type="button" variant="outline" onClick={replay}>
                  <RotateCcw data-icon="inline-start" />重新播放演示
                </Button>
              )}
            </>
          )}
        </div>
      </div>

      <DemoTimeline frames={scenario.frames} frameIndex={state.frameIndex} onFrameChange={goToFrame} />
    </section>
  );
}
