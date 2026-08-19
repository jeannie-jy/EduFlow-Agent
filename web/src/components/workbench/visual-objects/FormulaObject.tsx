/**
 * FormulaObject — LaTeX 公式可视化。
 * DSL VisualObject type="formula"
 *
 * 使用 KaTeX 渲染，并在异常输入时回退为可读文本。
 */

import { memo, useMemo } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";
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
  const expression = latex || label;
  const renderedFormula = useMemo(() => {
    if (!expression) return "";
    try {
      return katex.renderToString(expression, {
        displayMode: true,
        output: "htmlAndMathml",
        strict: "ignore",
        throwOnError: false,
        trust: false,
      });
    } catch {
      return "";
    }
  }, [expression]);

  if (!latex && !label) {
    return (
      <span className={cn("text-xs text-muted-foreground italic", className)}>
        (空公式)
      </span>
    );
  }

  if (!renderedFormula) {
    return (
      <div className={cn("max-w-full overflow-x-auto rounded-md border bg-muted/30 px-3 py-2 font-mono text-sm", className)}>
        {expression}
      </div>
    );
  }

  return (
    <div
      className={cn(
        "formula-object max-w-full overflow-x-auto rounded-md border bg-muted/30 px-3 py-2 text-center text-sm",
        className,
      )}
      aria-label={label || "数学公式"}
      dangerouslySetInnerHTML={{ __html: renderedFormula }}
    />
  );
});

export default FormulaObject;
