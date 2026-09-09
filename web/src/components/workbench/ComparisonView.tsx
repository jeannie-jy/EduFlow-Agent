/**
 * ComparisonView — 算法对比面板。
 *
 * 展示多算法的并排对比表和场景分析。
 */

import { CheckCircle2, TriangleAlert, ClipboardList } from "lucide-react";
import { cn } from "@/lib/utils";

// ============================================================================
// 类型
// ============================================================================

export interface ComparisonAlgorithm {
  name: string;
  description: string;
  pros: string[];
  cons: string[];
}

export interface ComparisonData {
  topic: string;
  algorithms: ComparisonAlgorithm[];
  dimensions: string[];
  comparison_table: Record<string, string>[];
  scenario_analysis: string;
}

export interface ComparisonViewProps {
  data: ComparisonData;
}

// ============================================================================
// 组件
// ============================================================================

export function ComparisonView({ data }: ComparisonViewProps) {
  const { topic, algorithms, dimensions, comparison_table: table, scenario_analysis } = data;
  const algoNames = algorithms.map((a) => a.name);

  if (algorithms.length === 0) {
    return (
      <div className="flex items-center justify-center p-8 text-[var(--muted-foreground)]">
        暂无对比数据
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 p-4">
      {/* 标题 */}
      <div>
        <h3 className="text-lg font-bold text-[var(--foreground)]">{topic}</h3>
        <p className="mt-1 text-sm text-[var(--muted-foreground)]">
          共对比 {algorithms.length} 个算法，{dimensions.length} 个维度
        </p>
      </div>

      {/* 算法简介卡片 */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {algorithms.map((algo) => (
          <div
            key={algo.name}
            className="rounded-lg border border-gray-200 p-4 dark:border-gray-700"
          >
            <h4 className="font-semibold text-[var(--foreground)]">{algo.name}</h4>
            <p className="mt-1 text-xs text-[var(--muted-foreground)]">{algo.description}</p>

            <div className="mt-3 space-y-2">
              <div>
                <p className="flex items-center gap-1 text-xs font-medium text-[var(--success)]"><CheckCircle2 size={13} aria-label="优点" /> 优点</p>
                <ul className="mt-1 list-inside list-disc text-xs text-[var(--foreground)]/80 space-y-0.5">
                  {algo.pros.map((p, i) => <li key={i}>{p}</li>)}
                </ul>
              </div>
              <div>
                <p className="flex items-center gap-1 text-xs font-medium text-[var(--error)]"><TriangleAlert size={13} aria-label="缺点" /> 缺点</p>
                <ul className="mt-1 list-inside list-disc text-xs text-[var(--foreground)]/80 space-y-0.5">
                  {algo.cons.map((c, i) => <li key={i}>{c}</li>)}
                </ul>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* 对比表格 */}
      <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-800">
              <th className="px-4 py-2.5 text-left font-medium text-gray-600 dark:text-gray-300">
                对比维度
              </th>
              {algoNames.map((name) => (
                <th
                  key={name}
                  className="px-4 py-2.5 text-left font-medium text-gray-600 dark:text-gray-300"
                >
                  {name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.map((row, i) => (
              <tr
                key={i}
                className={cn(
                  "border-b border-[var(--border)]",
                  i % 2 === 0 && "bg-[var(--card)]",
                  i % 2 === 1 && "bg-[var(--secondary)]/50",
                )}
              >
                <td className="px-4 py-2.5 font-medium text-[var(--foreground)]">
                  {row.dimension}
                </td>
                {algoNames.map((name) => (
                  <td
                    key={name}
                    className="px-4 py-2.5 text-[var(--foreground)]/80"
                  >
                    {row[name] ?? "—"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 场景分析 */}
      <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 dark:border-blue-800 dark:bg-blue-950">
        <h4 className="flex items-center gap-1 text-sm font-semibold text-[var(--interactive)] mb-2">
          <ClipboardList size={14} aria-label="选型建议" /> 选型建议
        </h4>
        <p className="text-sm text-[var(--interactive)] leading-relaxed">
          {scenario_analysis}
        </p>
      </div>
    </div>
  );
}
