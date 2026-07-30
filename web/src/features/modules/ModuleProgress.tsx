/**
 * ModuleProgress — 多模块并行进度显示。
 *
 * 显示每个模块的生成状态（等待/进行中/完成/错误），
 * 以及整体进度条。
 */

import { CheckCircle2, XCircle, Loader2, Clock } from "lucide-react";
import type { ModuleInfo } from "@/services/generate";

// ============================================================================
// 类型
// ============================================================================

export interface ModuleProgressItem {
  module_id: string;
  display_name: string;
  status: "pending" | "running" | "done" | "error";
  error?: string;
}

export interface ModuleProgressProps {
  modules: ModuleProgressItem[];
  totalPct?: number;
}

// ============================================================================
// 组件
// ============================================================================

export function ModuleProgress({ modules, totalPct = 0 }: ModuleProgressProps) {
  const doneCount = modules.filter((m) => m.status === "done").length;
  const errorCount = modules.filter((m) => m.status === "error").length;
  const runningCount = modules.filter((m) => m.status === "running").length;
  const total = modules.length;

  return (
    <div className="flex flex-col gap-4">
      {/* 总体进度 */}
      <div className="flex flex-col gap-1">
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-600 dark:text-gray-400">
            {runningCount > 0
              ? `正在生成 (${doneCount}/${total})...`
              : errorCount > 0
                ? `完成 (${doneCount} 成功, ${errorCount} 失败)`
                : `已完成 ${doneCount}/${total} 个模块`}
          </span>
          <span className="text-gray-500 dark:text-gray-400 tabular-nums">
            {totalPct}%
          </span>
        </div>
        {/* 进度条 */}
        <div className="h-2 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
          <div
            className="h-full rounded-full bg-blue-500 transition-all duration-500"
            style={{ width: `${totalPct}%` }}
          />
        </div>
      </div>

      {/* 各模块状态列表 */}
      <ul className="flex flex-col gap-2">
        {modules.map((mod) => (
          <li
            key={mod.module_id}
            className="flex items-center gap-3 rounded-md border border-gray-200 px-3 py-2 text-sm dark:border-gray-700"
          >
            {/* 状态图标 */}
            {mod.status === "pending" && (
              <Clock className="h-4 w-4 text-gray-400" />
            )}
            {mod.status === "running" && (
              <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
            )}
            {mod.status === "done" && (
              <CheckCircle2 className="h-4 w-4 text-green-500" />
            )}
            {mod.status === "error" && (
              <XCircle className="h-4 w-4 text-red-500" />
            )}

            {/* 模块名称 */}
            <span
              className={`flex-1 ${
                mod.status === "done"
                  ? "text-gray-900 dark:text-gray-100"
                  : mod.status === "error"
                    ? "text-red-600 dark:text-red-400"
                    : "text-gray-500 dark:text-gray-400"
              }`}
            >
              {mod.display_name}
            </span>

            {/* 错误信息 */}
            {mod.status === "error" && mod.error && (
              <span
                className="max-w-[200px] truncate text-xs text-red-400"
                title={mod.error}
              >
                {mod.error}
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
