/**
 * 表格可视化组件（TableObject）。
 *
 * 渲染 DSL VisualObject type="table" 的 HTML <table>，
 * 单元格可单独高亮，支持值变化闪烁。
 *
 * 对齐：设计文档 7.1.4 节。
 */

import { memo, useMemo } from "react";
import { cn } from "@/lib/utils";
import type { DSLVisualObject } from "../simulation-model";

export type TableObjectProps = {
  object: DSLVisualObject;
  /** 之前的值映射（用于检测变化），key 为 "row,col" */
  previousValues?: Record<string, unknown>;
  /** 高亮行索引集合 */
  highlightRows?: Set<number>;
  /** 高亮列索引集合 */
  highlightCols?: Set<number>;
  className?: string;
};

export const TableObject = memo(function TableObject({
  object,
  previousValues,
  highlightRows,
  highlightCols,
  className,
}: TableObjectProps) {
  const headers = (object.headers ?? []) as string[];
  const rows = (object.rows ?? []) as unknown[][];

  const hasData = headers.length > 0 || rows.length > 0;

  if (!hasData) {
    return (
      <div className={cn("text-xs text-muted-foreground", className)} aria-label="空表格">
        (空表格)
      </div>
    );
  }

  return (
    <div className={cn("overflow-hidden rounded-lg border", className)}>
      <table className="w-full text-sm" aria-label={object.label ?? "数据表格"}>
        {headers.length > 0 && (
          <thead>
            <tr className="bg-muted/50">
              {headers.map((header, colIdx) => (
                <th
                  key={colIdx}
                  className={cn(
                    "border-b px-3 py-2 text-left font-medium text-muted-foreground",
                    highlightCols?.has(colIdx) && "bg-primary/10",
                  )}
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
        )}
        <tbody>
          {rows.map((row, rowIdx) => (
            <tr
              key={rowIdx}
              className={cn(
                "border-b last:border-b-0",
                rowIdx % 2 === 0 && "bg-muted/20",
                highlightRows?.has(rowIdx) && "bg-primary/5 ring-1 ring-primary/20",
              )}
            >
              {row.map((cell, colIdx) => {
                const cellKey = `${rowIdx},${colIdx}`;
                const prevValue = previousValues?.[cellKey];
                const changed = prevValue !== undefined && prevValue !== cell;
                const cellStr = cell == null ? "" : String(cell);

                return (
                  <td
                    key={colIdx}
                    className={cn(
                      "px-3 py-2 tabular-nums",
                      changed && "animate-update-value",
                      highlightCols?.has(colIdx) && "bg-primary/5",
                    )}
                    aria-label={headers[colIdx] ? `${headers[colIdx]}: ${cellStr}` : cellStr}
                  >
                    {cellStr}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
});

export default TableObject;