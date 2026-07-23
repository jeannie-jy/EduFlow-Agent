/**
 * TimelineObject — 时间线可视化。
 * DSL VisualObject type="timeline"
 */

import { memo } from "react";
import { cn } from "@/lib/utils";
import type { DSLVisualObject } from "../simulation-model";

export type TimelineObjectProps = {
  object: DSLVisualObject;
  className?: string;
};

export const TimelineObject = memo(function TimelineObject({
  object,
  className,
}: TimelineObjectProps) {
  const events = (object.events as Record<string, unknown>[]) ?? [];
  const label = object.label ?? "";

  if (events.length === 0) {
    return (
      <div className={cn("text-xs text-muted-foreground", className)} aria-label="空时间线">
        (空)
      </div>
    );
  }

  return (
    <div className={cn("space-y-0", className)} aria-label={label || "时间线"}>
      {events.map((evt, idx) => {
        const time = evt.time ?? evt.t ?? `T${idx}`;
        const desc = evt.description ?? evt.label ?? evt.desc ?? "";
        const isActive = evt.active ?? evt.current ?? false;

        return (
          <div key={idx} className="flex items-start gap-3 text-xs">
            {/* 时间轴线 */}
            <div className="flex flex-col items-center shrink-0 pt-0.5">
              <div
                className={cn(
                  "size-2 rounded-full border-2",
                  isActive ? "border-primary bg-primary" : "border-muted-foreground/30",
                )}
              />
              {idx < events.length - 1 && (
                <div className="w-px h-full min-h-[16px] bg-border mt-0.5" />
              )}
            </div>
            <div className="pb-2">
              <span className="font-mono text-[10px] text-muted-foreground mr-1.5">
                {String(time)}
              </span>
              <span className={cn(isActive && "font-medium text-primary")}>
                {String(desc)}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
});

export default TimelineObject;
