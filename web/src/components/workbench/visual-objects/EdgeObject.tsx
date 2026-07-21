/**
 * EdgeObject — 有向/无向边可视化。
 * DSL VisualObject type="edge"
 */

import { memo } from "react";
import { cn } from "@/lib/utils";
import type { DSLVisualObject } from "../simulation-model";

export type EdgeObjectProps = {
  object: DSLVisualObject;
  className?: string;
};

export const EdgeObject = memo(function EdgeObject({
  object,
  className,
}: EdgeObjectProps) {
  const label = object.label ?? "";
  const style = object.style ?? {};
  const weight = object.weight as number | undefined;
  const directed = (object.directed as boolean) ?? true;
  const color = (style.color as string) ?? "var(--graph-line)";
  const strokeWidth = (style.width as number) ?? 2;

  return (
    <div
      className={cn("flex items-center gap-1 text-xs font-mono", className)}
      aria-label={`边 ${label}${weight != null ? ` 权重 ${weight}` : ""}`}
    >
      <svg
        width="60"
        height="16"
        viewBox="0 0 60 16"
        className="shrink-0"
        aria-hidden="true"
      >
        <line
          x1={directed ? 4 : 0}
          y1={8}
          x2={56}
          y2={8}
          stroke={color}
          strokeWidth={strokeWidth}
          markerEnd={directed ? "url(#arrowhead)" : undefined}
        />
        {directed && (
          <defs>
            <marker
              id="arrowhead"
              markerWidth="8"
              markerHeight="6"
              refX="8"
              refY="3"
              orient="auto"
            >
              <polygon points="0 0, 8 3, 0 6" fill={color} />
            </marker>
          </defs>
        )}
      </svg>
      <span className="text-muted-foreground whitespace-nowrap">
        {label}
        {weight != null && <> ({weight})</>}
      </span>
    </div>
  );
});

export default EdgeObject;
