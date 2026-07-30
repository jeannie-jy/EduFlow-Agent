/**
 * ModuleCard — 单个模块选择卡片。
 *
 * 展示模块图标、名称、描述，支持勾选/取消勾选。
 */

import { Check } from "lucide-react";
import type { ModuleInfo } from "@/services/generate";

// ============================================================================
// 图标映射
// ============================================================================

const ICON_MAP: Record<string, string> = {
  mindmap: "🧠",
  cards: "🃏",
  quiz: "✏️",
  frames: "🎬",
  video: "🎥",
  comparison: "⚖️",
  misconception: "⚠️",
  pathway: "🗺️",
  sandbox: "💻",
  pptx: "📊",
  tts: "🔊",
};

const CATEGORY_LABELS: Record<string, string> = {
  visual: "可视化",
  interactive: "交互",
  export: "导出",
};

// ============================================================================
// 类型
// ============================================================================

export type ModuleStatus = "available" | "pending" | "running" | "done" | "error";

export interface ModuleCardProps {
  info: ModuleInfo;
  selected: boolean;
  onToggle: () => void;
  status?: ModuleStatus;
}

// ============================================================================
// 组件
// ============================================================================

export function ModuleCard({ info, selected, onToggle, status = "available" }: ModuleCardProps) {
  const isDisabled = status === "running" || status === "done";
  const icon = ICON_MAP[info.icon] ?? "📦";

  return (
    <button
      type="button"
      onClick={onToggle}
      disabled={isDisabled}
      className={`
        relative flex flex-col gap-2 rounded-lg border-2 p-4 text-left transition-all
        ${selected
          ? "border-blue-500 bg-blue-50 ring-2 ring-blue-200 dark:border-blue-400 dark:bg-blue-950 dark:ring-blue-800"
          : "border-gray-200 bg-white hover:border-gray-300 dark:border-gray-700 dark:bg-gray-900 dark:hover:border-gray-600"
        }
        ${isDisabled ? "cursor-not-allowed opacity-60" : "cursor-pointer"}
        ${status === "running" ? "animate-pulse" : ""}
      `}
    >
      {/* 选中标记 */}
      {selected && (
        <span className="absolute right-2 top-2 flex h-5 w-5 items-center justify-center rounded-full bg-blue-500">
          <Check className="h-3 w-3 text-white" strokeWidth={3} />
        </span>
      )}

      {/* 状态指示器 */}
      {status === "running" && (
        <span className="absolute right-2 top-2 flex h-5 w-5 items-center justify-center">
          <span className="h-3 w-3 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
        </span>
      )}
      {status === "done" && (
        <span className="absolute right-2 top-2 flex h-5 w-5 items-center justify-center rounded-full bg-green-500">
          <Check className="h-3 w-3 text-white" strokeWidth={3} />
        </span>
      )}
      {status === "error" && (
        <span className="absolute right-2 top-2 flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-xs text-white">
          !
        </span>
      )}

      {/* 图标 + 标题 */}
      <span className="text-2xl">{icon}</span>
      <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">
        {info.display_name}
      </span>

      {/* 描述 */}
      <span className="text-xs text-gray-500 dark:text-gray-400 line-clamp-2">
        {info.description}
      </span>

      {/* 底部分类标签 */}
      <span className="mt-auto text-xs text-gray-400 dark:text-gray-500">
        {CATEGORY_LABELS[info.category] ?? info.category}
      </span>
    </button>
  );
}
