/**
 * StepIndicator — 线性步骤指示器。
 *
 * 替代顶部 Tab 栏，展示 1→2→3 的单向流程。
 * 对齐 DESIGN.md：纸本质感、语义色、编辑式排版。
 */

import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

export type StepId = "select" | "plan" | "results";

const STEPS: { id: StepId; label: string; num: number }[] = [
  { id: "select", label: "选择模块", num: 1 },
  { id: "plan", label: "教学计划", num: 2 },
  { id: "results", label: "成果预览", num: 3 },
];

export interface StepIndicatorProps {
  current: StepId;
  completed: StepId[];
}

export function StepIndicator({ current, completed }: StepIndicatorProps) {
  return (
    <nav className="flex items-center justify-center gap-2 px-4 py-3 border-b border-[var(--border)]" aria-label="生成流程">
      {STEPS.map((step, i) => {
        const isCompleted = completed.includes(step.id);
        const isCurrent = current === step.id;
        return (
          <div key={step.id} className="flex items-center gap-2">
            {/* 步骤节点 */}
            <div
              className={cn(
                "flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm transition-colors",
                isCurrent && "bg-[var(--interactive)]/10 text-[var(--interactive)] font-semibold",
                isCompleted && !isCurrent && "text-[var(--success)]",
                !isCurrent && !isCompleted && "text-[var(--muted-foreground)]",
              )}
            >
              <span
                className={cn(
                  "flex h-5 w-5 items-center justify-center rounded-full text-xs font-mono",
                  isCurrent && "bg-[var(--interactive)] text-white",
                  isCompleted && "bg-[var(--success)] text-white",
                  !isCurrent && !isCompleted && "border border-[var(--border)] text-[var(--muted-foreground)]",
                )}
              >
                {isCompleted ? <Check size={12} strokeWidth={3} /> : step.num}
              </span>
              <span className="hidden sm:inline">{step.label}</span>
            </div>
            {/* 连接线 */}
            {i < STEPS.length - 1 && (
              <div
                className={cn(
                  "h-px w-6 sm:w-10",
                  isCompleted || (isCurrent && step.id !== "results")
                    ? "bg-[var(--interactive)]"
                    : "bg-[var(--border)]",
                )}
              />
            )}
          </div>
        );
      })}
    </nav>
  );
}
