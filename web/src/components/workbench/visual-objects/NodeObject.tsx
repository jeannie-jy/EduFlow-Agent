/**
 * NodeObject — 圆形/方形节点可视化。
 * DSL VisualObject type="node"
 */

import { memo } from "react";
import { cn } from "@/lib/utils";
import type { DSLVisualObject } from "../simulation-model";

export type NodeObjectProps = {
  object: DSLVisualObject;
  className?: string;
};

const SHAPE_STYLES: Record<string, string> = {
  circle: "rounded-full",
  square: "rounded-md",
  diamond: "rounded-md rotate-45",
};

export const NodeObject = memo(function NodeObject({
  object,
  className,
}: NodeObjectProps) {
  const label = object.label ?? "";
  const style = object.style ?? {};
  const nodeType = (object.node_type as string) ?? "circle";
  const color = (style.color as string) ?? "var(--graph-active)";
  const size = (style.size as number) ?? 40;

  return (
    <div
      className={cn(
        "flex items-center justify-center shrink-0",
        SHAPE_STYLES[nodeType] ?? SHAPE_STYLES.circle,
        className,
      )}
      style={{
        width: size,
        height: size,
        backgroundColor: color,
        color: "#fff",
        fontSize: Math.max(10, size * 0.35),
        fontWeight: 700,
      }}
      title={label}
      aria-label={`节点 ${label}`}
    >
      {nodeType === "diamond" ? (
        <span className="-rotate-45">{label.slice(0, 2)}</span>
      ) : (
        label.slice(0, 2)
      )}
    </div>
  );
});

export default NodeObject;
