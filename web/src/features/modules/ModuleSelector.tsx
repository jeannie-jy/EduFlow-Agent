/**
 * ModuleSelector — 模块选择器主组件。
 *
 * 教学计划审批通过后，展示所有可用模块供用户勾选。
 * 用户提交后触发模块生成流程。
 */

import { useState, useCallback } from "react";
import { Sparkles, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ModuleCard } from "./ModuleCard";
import type { ModuleInfo } from "@/services/generate";
import type { ModuleStatus } from "./ModuleCard";

// ============================================================================
// 类型
// ============================================================================

export interface ModuleSelectorProps {
  modules: ModuleInfo[];
  onStart: (selectedIds: string[]) => void;
  loading?: boolean;
  /** 可选：预设选中的模块 ID */
  defaultSelected?: string[];
  /** 是否显示开始生成按钮（审批阶段复用时不显示） */
  showStartButton?: boolean;
}

// ============================================================================
// 组件
// ============================================================================

export function ModuleSelector({
  modules,
  onStart,
  loading = false,
  defaultSelected,
  showStartButton = true,
}: ModuleSelectorProps) {
  const [selected, setSelected] = useState<Set<string>>(
    () => new Set(defaultSelected ?? ["frames"])
  );

  const toggle = useCallback((moduleId: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(moduleId)) {
        next.delete(moduleId);
      } else {
        next.add(moduleId);
      }
      return next;
    });
  }, []);

  const handleStart = useCallback(() => {
    if (selected.size > 0) {
      onStart([...selected]);
    }
  }, [selected, onStart]);

  return (
    <div className="flex flex-col gap-6 p-4">
      {/* 标题 */}
      <div className="flex flex-col gap-1">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          选择生成的产出形式
        </h3>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          教学计划已生成，请选择你需要的产出物。不同模块可独立生成和编辑。
        </p>
      </div>

      {/* 模块卡片网格 */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {modules.map((mod) => (
          <ModuleCard
            key={mod.module_id}
            info={mod}
            selected={selected.has(mod.module_id)}
            onToggle={() => toggle(mod.module_id)}
          />
        ))}
      </div>

      {/* 提交按钮（审批阶段复用时不显示） */}
      {showStartButton && (
      <div className="flex items-center justify-between border-t border-gray-200 pt-4 dark:border-gray-700">
        <span className="text-sm text-gray-500 dark:text-gray-400">
          已选择 {selected.size} 个模块
        </span>
        <Button
          onClick={handleStart}
          disabled={selected.size === 0 || loading}
          className="min-w-[140px]"
        >
          {loading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              生成中...
            </>
          ) : (
            <>
              <Sparkles className="mr-2 h-4 w-4" />
              开始生成 ({selected.size})
            </>
          )}
        </Button>
      </div>
      )}
    </div>
  );
}
