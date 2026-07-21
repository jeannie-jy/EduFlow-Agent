/**
 * FormulaObject — LaTeX 公式可视化。
 * DSL VisualObject type="formula"
 *
 * 当前使用纯文本渲染，后续可集成 KaTeX。
 */

import { memo } from "react";
import { cn } from "@/lib/utils";
import type { DSLVisualObject } from "../simulation-model";

export type FormulaObjectProps = {
  object: DSLVisualObject;
  className?: string;
};

export const FormulaObject = memo(function FormulaObject({
  object,
  className,
}: FormulaObjectProps) {
  const latex = (object.latex as string) ?? "";
  const label = object.label ?? "";

  if (!latex && !label) {
    return (
      <span className={cn("text-xs text-muted-foreground italic", className)}>
        (空公式)
      </span>
    );
  }

  return (
    <div
      className={cn(
        "inline-block rounded-md border bg-muted/30 px-3 py-1.5 font-mono text-sm",
        className,
      )}
      aria-label={label || `公式: ${latex}`}
    >
      {latex || label}
    </div>
  );
});

export default FormulaObject;
