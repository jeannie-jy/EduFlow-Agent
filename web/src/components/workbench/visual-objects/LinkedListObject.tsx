/**
 * LinkedListObject — 链表可视化。
 * DSL VisualObject type="linked_list"
 */

import { memo } from "react";
import { cn } from "@/lib/utils";
import type { DSLVisualObject } from "../simulation-model";

export type LinkedListObjectProps = {
  object: DSLVisualObject;
  className?: string;
};

export const LinkedListObject = memo(function LinkedListObject({
  object,
  className,
}: LinkedListObjectProps) {
  const nodes = (object.nodes as Record<string, unknown>[]) ?? [];
  const label = object.label ?? "";

  if (nodes.length === 0) {
    return (
      <div className={cn("text-xs text-muted-foreground", className)} aria-label="空链表">
        null
      </div>
    );
  }

  return (
    <div className={cn("inline-flex items-center gap-0", className)} aria-label={label || "链表"}>
      {nodes.map((node, idx) => {
        const val = node.value ?? node.label ?? node.data ?? `N${idx}`;
        const isHead = Boolean(node.head ?? (idx === 0));
        const isTail = Boolean(node.tail ?? (idx === nodes.length - 1));
        const color =
          typeof node.color === "string"
            ? node.color
            : "var(--graph-active)";
        const key =
          typeof node.id === "string" ||
          typeof node.id === "number" ||
          typeof node.id === "bigint"
            ? node.id
            : idx;

        return (
          <div key={key} className="flex items-center">
            {/* 节点 */}
            <div
              className={cn(
                "flex items-center gap-0.5 rounded-md border px-2 py-1 text-xs font-mono",
                isHead && "border-primary ring-1 ring-primary/20",
                isTail && "border-success ring-1 ring-success/20",
              )}
              style={{ borderColor: isHead || isTail ? undefined : color }}
            >
              <span className="tabular-nums">{String(val)}</span>
              {Boolean(node.next) && (
                <span className="text-muted-foreground text-[10px]">→</span>
              )}
            </div>
            {/* 箭头 */}
            {idx < nodes.length - 1 && (
              <span className="mx-0.5 text-muted-foreground text-xs">→</span>
            )}
          </div>
        );
      })}
    </div>
  );
});

export default LinkedListObject;
