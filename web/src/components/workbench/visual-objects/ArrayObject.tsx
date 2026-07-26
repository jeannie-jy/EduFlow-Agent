/**
 * 数组可视化组件（ArrayObject）。
 *
 * 渲染 DSL VisualObject type="array" 的 DOM flex 排列，
 * 每个 cell 是一个 div，支持值变化时的闪烁动画。
 *
 * 对齐：设计文档 7.1.4 节。
 */

import { memo, useMemo } from "react";
import { cn } from "@/lib/utils";
import type { DSLVisualObject } from "../simulation-model";

export type ArrayObjectProps = {
  object: DSLVisualObject;
  /** 之前的值映射（用于检测变化），key 为 cell index */
  previousValues?: Record<string, unknown>;
  className?: string;
};

function getCellKey(value: unknown, fallback: string | number) {
  return typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "bigint"
    ? value
    : fallback;
}

export const ArrayObject = memo(function ArrayObject({
  object,
  previousValues,
  className,
}: ArrayObjectProps) {
  const cells = object.cells ?? [];
  const style = object.style ?? {};

  const cellEntries = useMemo(
    () =>
      cells.map((cell, idx) => {
        const value = cell.value ?? cell.label ?? cell.text ?? "";
        const prevValue = previousValues?.[String(idx)];
        const changed = prevValue !== undefined && prevValue !== value;
        const nestedColor =
          typeof cell.style === "object" &&
          cell.style !== null &&
          "color" in cell.style
            ? cell.style.color
            : undefined;
        const color = cell.color ?? nestedColor ?? style.color;
        const cellColor = typeof color === "string" ? color : undefined;

        return {
          key: getCellKey(cell.id, String(idx)),
          value,
          changed,
          cellColor,
          highlight: cell.highlight ?? false,
        };
      }),
    [cells, previousValues, style.color],
  );

  if (cells.length === 0) {
    return (
      <div className={cn("flex items-center gap-0.5", className)} aria-label="空数组">
        <span className="text-xs text-muted-foreground">[ ]</span>
      </div>
    );
  }

  return (
    <div
      className={cn("inline-flex items-stretch rounded-md border", className)}
      role="list"
      aria-label={object.label ?? "数组"}
    >
      {cellEntries.map((cell, idx) => (
        <div
          key={cell.key}
          role="listitem"
          aria-label={`索引 ${idx}: ${cell.value}`}
          className={cn(
            "flex min-w-[2.5rem] items-center justify-center border-r px-3 py-1.5 text-sm font-mono tabular-nums",
            "last:border-r-0",
            // 变化闪烁动画
            cell.changed && "animate-update-value",
            // 高亮
            cell.highlight && "bg-primary/10 ring-2 ring-primary/30",
            // 交替背景色
            idx % 2 === 0 ? "bg-muted/30" : "bg-transparent",
          )}
          style={cell.cellColor ? { borderColor: cell.cellColor } : undefined}
        >
          {String(cell.value)}
        </div>
      ))}
      {/* 索引标签 */}
      <div className="flex border-t" role="presentation">
        {cells.map((cell, idx) => (
          <div
            key={getCellKey(cell.id, idx)}
            className="flex min-w-[2.5rem] items-center justify-center border-r px-1 py-0.5 text-[10px] text-muted-foreground last:border-r-0"
          >
            {idx}
          </div>
        ))}
      </div>
    </div>
  );
});

export default ArrayObject;
