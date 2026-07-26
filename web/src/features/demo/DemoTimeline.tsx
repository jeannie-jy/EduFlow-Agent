import { cn } from "@/lib/utils";
import type { SimulationFrame } from "@/components/workbench/simulation-model";

type DemoTimelineProps = {
  frames: SimulationFrame[];
  frameIndex: number;
  onFrameChange(frameIndex: number): void;
};

export function DemoTimeline({ frames, frameIndex, onFrameChange }: DemoTimelineProps) {
  return (
    <section aria-label="Dijkstra 推演进度" className="demo-timeline">
      <div className="demo-timeline__header">
        <p className="demo-eyebrow">推演进度</p>
        <p className="demo-timeline__count">{String(frameIndex + 1).padStart(2, "0")} / {String(frames.length).padStart(2, "0")}</p>
      </div>
      <ol className="demo-timeline__track">
        {frames.map((frame, index) => (
          <li key={frame.id} className={cn("demo-timeline__item", index === frameIndex && "is-current", index < frameIndex && "is-complete")}>
            <button
              type="button"
              aria-label={`跳到第 ${index + 1} 帧`}
              aria-current={index === frameIndex ? "step" : undefined}
              onClick={() => onFrameChange(index)}
            >
              <span aria-hidden="true">{index + 1}</span>
            </button>
            <p>第 {index + 1} 帧</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
