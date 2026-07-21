/**
 * ProcessObject — 进程控制块可视化。
 * DSL VisualObject type="process"
 */

import { memo } from "react";
import { cn } from "@/lib/utils";
import type { DSLVisualObject } from "../simulation-model";

export type ProcessObjectProps = {
  object: DSLVisualObject;
  className?: string;
};

const STATE_COLORS: Record<string, string> = {
  running: "border-success text-success",
  ready: "border-warning text-warning",
  blocked: "border-destructive text-destructive",
  terminated: "border-muted-foreground text-muted-foreground",
};

export const ProcessObject = memo(function ProcessObject({
  object,
  className,
}: ProcessObjectProps) {
  const pid = (object.pid as string) ?? "?";
  const state = (object.state as string) ?? "ready";
  const attrs = (object.attributes as Record<string, unknown>) ?? {};
  const label = object.label ?? `PID ${pid}`;

  return (
    <div
      className={cn(
        "inline-flex flex-col rounded-lg border p-3 text-sm min-w-[120px]",
        STATE_COLORS[state] ?? "border-border",
        className,
      )}
      aria-label={label}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-bold font-mono">PID {String(pid)}</span>
        <span className={cn(
          "rounded-full px-1.5 py-0.5 text-[10px] font-medium uppercase",
          state === "running" && "bg-success/10",
          state === "ready" && "bg-warning/10",
          state === "blocked" && "bg-destructive/10",
          state === "terminated" && "bg-muted",
        )}>
          {state}
        </span>
      </div>
      {Object.keys(attrs).length > 0 && (
        <div className="mt-2 space-y-0.5 text-xs text-muted-foreground">
          {Object.entries(attrs).slice(0, 4).map(([k, v]) => (
            <div key={k} className="flex justify-between gap-2">
              <span>{k}</span>
              <span className="tabular-nums font-mono">{String(v)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
});

export default ProcessObject;
