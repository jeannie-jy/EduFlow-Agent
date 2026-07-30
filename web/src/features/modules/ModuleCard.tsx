/**
 * ModuleCard — 单个模块选择卡片。
 *
 * 展示模块图标、名称、描述，支持勾选/取消勾选。
 * 对齐 DESIGN.md：纸本表面 + 语义色 + lucide 图标（无 Emoji）。
 */

import { Check, Brain, Layers, PenTool, Play, Video, GitCompare, AlertTriangle, Map, Code2, FileText, Volume2, Box } from "lucide-react";
import type { ModuleInfo } from "@/services/generate";

const ICON_MAP: Record<string, typeof Brain> = {
  mindmap: Brain, cards: Layers, quiz: PenTool, frames: Play,
  video: Video, comparison: GitCompare, misconception: AlertTriangle,
  pathway: Map, sandbox: Code2, pptx: FileText, tts: Volume2,
};

const CATEGORY_LABELS: Record<string, string> = {
  visual: "可视化", interactive: "交互", export: "导出",
};

export type ModuleStatus = "available" | "pending" | "running" | "done" | "error";

export interface ModuleCardProps {
  info: ModuleInfo;
  selected: boolean;
  onToggle: () => void;
  status?: ModuleStatus;
}

export function ModuleCard({ info, selected, onToggle, status = "available" }: ModuleCardProps) {
  const isDisabled = status === "running" || status === "done";
  const IconComponent = ICON_MAP[info.icon] ?? Box;

  return (
    <button
      type="button" onClick={onToggle} disabled={isDisabled}
      className={`
        relative flex flex-col gap-2 rounded-lg border-2 p-4 text-left transition-all duration-200
        ${selected
          ? "border-[var(--interactive)] bg-[var(--interactive)]/10"
          : "border-[var(--border)] bg-[var(--card)] hover:border-[var(--interactive)]/40"
        }
        ${isDisabled ? "cursor-not-allowed opacity-60" : "cursor-pointer"}
        ${status === "running" ? "animate-pulse" : ""}
      `}
    >
      {selected && (
        <span className="absolute right-2 top-2 flex h-5 w-5 items-center justify-center rounded-full bg-[var(--interactive)]">
          <Check className="h-3 w-3 text-[var(--card)]" strokeWidth={3} />
        </span>
      )}

      {status === "running" && (
        <span className="absolute right-2 top-2 flex h-5 w-5 items-center justify-center">
          <span className="h-3 w-3 animate-spin rounded-full border-2 border-[var(--interactive)] border-t-transparent" />
        </span>
      )}
      {status === "done" && (
        <span className="absolute right-2 top-2 flex h-5 w-5 items-center justify-center rounded-full bg-[var(--success)]">
          <Check className="h-3 w-3 text-[var(--card)]" strokeWidth={3} />
        </span>
      )}
      {status === "error" && (
        <span className="absolute right-2 top-2 flex h-5 w-5 items-center justify-center rounded-full bg-[var(--error)] text-xs text-[var(--card)]">!</span>
      )}

      <IconComponent size={24} className="text-[var(--interactive)]" />
      <span className="text-sm font-semibold text-[var(--foreground)]">{info.display_name}</span>
      <span className="text-xs text-[var(--muted-foreground)] line-clamp-2">{info.description}</span>
      <span className="mt-auto text-xs text-[var(--muted-foreground)]/60">
        {CATEGORY_LABELS[info.category] ?? info.category}
      </span>
    </button>
  );
}
