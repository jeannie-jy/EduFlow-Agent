import { CheckIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { AiStatusStrip, type GenerationState } from "./AiStatusStrip";

const planSteps = [
  { title: "初始化", description: "设置源点与初始距离" },
  { title: "选择最小距离节点", description: "选择当前最优节点" },
  { title: "松弛邻接边", description: "更新相邻节点距离" },
  { title: "重复直至完成", description: "所有节点确定最短距离" },
];

type PlanSequenceProps = {
  generation: GenerationState;
  activeStep: number;
  onStepChange: (step: number) => void;
};

export function PlanSequence({ generation, activeStep, onStepChange }: PlanSequenceProps) {
  return (
    <section aria-labelledby="plan-heading" className="shrink-0 overflow-hidden rounded-xl border bg-card px-3 py-3 shadow-[0_1px_2px_color-mix(in_oklch,var(--foreground)_4%,transparent)] sm:px-4">
      <div className="mb-2.5 flex items-center justify-between gap-4">
        <h2 id="plan-heading" className="text-xs font-medium tracking-wide text-muted-foreground">
          AI 推演计划
        </h2>
        <AiStatusStrip generation={generation} />
      </div>
      <ol className="no-scrollbar grid min-w-0 auto-cols-[minmax(10rem,1fr)] grid-flow-col grid-cols-none gap-2 overflow-x-auto pb-1 sm:auto-cols-auto sm:grid-flow-row sm:grid-cols-2 sm:overflow-visible sm:pb-0 lg:grid-cols-4" aria-label="教学路径">
        {planSteps.map((step, index) => {
          const number = index + 1;
          const complete = number < activeStep;
          const active = number === activeStep;
          return (
            <li key={step.title} className="relative min-w-0">
              {index < planSteps.length - 1 ? (
                <span
                  aria-hidden="true"
                  className={cn(
                    "absolute top-4 left-[calc(100%-0.35rem)] hidden h-px w-[calc(100%-2.25rem)] -translate-x-full lg:block",
                    complete ? "plan-flow-line" : "bg-border",
                  )}
                />
              ) : null}
              <button
                type="button"
                onClick={() => onStepChange(number)}
                aria-current={active ? "step" : undefined}
                className={cn(
                  "group relative z-10 flex w-full items-start gap-2.5 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-muted/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  active && "bg-accent/70",
                )}
              >
                <span
                  className={cn(
                    "flex size-7 shrink-0 items-center justify-center rounded-full border text-xs font-semibold tabular-nums",
                    complete && "border-primary bg-primary text-primary-foreground",
                    active && "border-primary bg-background text-primary ring-4 ring-primary/10",
                    !complete && !active && "bg-muted text-muted-foreground",
                  )}
                >
                  {complete ? <CheckIcon className="size-3.5" aria-hidden="true" /> : number}
                </span>
                <span className="min-w-0 pt-0.5">
                  <span className={cn("block truncate text-[13px] font-medium", active && "text-primary")}>{step.title}</span>
                  <span className="mt-0.5 block truncate text-[11px] text-muted-foreground">{step.description}</span>
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
