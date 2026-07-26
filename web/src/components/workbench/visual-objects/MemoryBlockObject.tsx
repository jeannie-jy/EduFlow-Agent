/**
 * MemoryBlockObject — 内存布局可视化。
 * DSL VisualObject type="memory_block"
 */

import { memo } from "react";
import { cn } from "@/lib/utils";
import type { DSLVisualObject } from "../simulation-model";

export type MemoryBlockObjectProps = {
  object: DSLVisualObject;
  className?: string;
};

export const MemoryBlockObject = memo(function MemoryBlockObject({
  object,
  className,
}: MemoryBlockObjectProps) {
  const blocks = (object.blocks as Record<string, unknown>[]) ?? [];
  const label = object.label ?? "";

  if (blocks.length === 0) {
    return (
      <div className={cn("text-xs text-muted-foreground", className)} aria-label="空内存">
        (空)
      </div>
    );
  }

  return (
    <div className={cn("inline-flex flex-col rounded-lg border text-xs font-mono", className)} aria-label={label || "内存布局"}>
      {blocks.map((block, idx) => {
        const addr = block.address ?? block.addr ?? `0x${(idx * 8).toString(16).padStart(4, "0")}`;
        const val = block.value ?? block.data ?? "";
        const allocated = Boolean(block.allocated ?? (block.free === false));
        const size = block.size ?? 8;
        const key =
          typeof block.id === "string" ||
          typeof block.id === "number" ||
          typeof block.id === "bigint"
            ? block.id
            : idx;

        return (
          <div
            key={key}
            className={cn(
              "flex items-center justify-between gap-3 border-b px-3 py-1.5 last:border-b-0",
              allocated ? "bg-muted/20" : "bg-destructive/5 text-destructive",
            )}
          >
            <span className="text-muted-foreground">{String(addr)}</span>
            <span className="tabular-nums">{String(val)}</span>
            <span className="text-[10px] text-muted-foreground">{String(size)}B</span>
          </div>
        );
      })}
    </div>
  );
});

export default MemoryBlockObject;
