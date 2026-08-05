/**
 * LearningPathway — 学习路径可视化。
 *
 * 展示前置→当前→进阶的路线图，含节点卡片和关系连线。
 */

import { BookOpen, ArrowRight, Lightbulb, Clock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

// ============================================================================
// 类型
// ============================================================================

export interface PathwayNode {
  id: string;
  name: string;
  type: "prerequisite" | "core" | "extension" | "related" | "application";
  description: string;
  difficulty?: number;
}

export interface PathwayEdge {
  source: string;
  target: string;
  relation: string;
}

export interface PathwayData {
  current_topic: string;
  nodes: PathwayNode[];
  edges: PathwayEdge[];
  estimated_hours?: number;
  learning_tips?: string[];
}

export interface LearningPathwayProps {
  data: PathwayData;
}

// ============================================================================
// 组件
// ============================================================================

const TYPE_CONFIG: Record<string, { label: string; color: string; icon: typeof BookOpen }> = {
  prerequisite: { label: "前置", color: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300", icon: BookOpen },
  core: { label: "核心", color: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300", icon: BookOpen },
  extension: { label: "进阶", color: "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300", icon: ArrowRight },
  related: { label: "相关", color: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300", icon: ArrowRight },
  application: { label: "应用", color: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300", icon: Lightbulb },
};

function groupByType(nodes: PathwayNode[]): Record<string, PathwayNode[]> {
  const groups: Record<string, PathwayNode[]> = {};
  for (const n of nodes) {
    (groups[n.type] ??= []).push(n);
  }
  return groups;
}

export function LearningPathway({ data }: LearningPathwayProps) {
  const { current_topic, nodes, learning_tips, estimated_hours } = data;

  if (nodes.length === 0) {
    return <div className="p-8 text-center text-[var(--muted-foreground)]">暂无学习路径数据</div>;
  }

  const grouped = groupByType(nodes);
  const order: string[] = ["prerequisite", "core", "extension", "related", "application"];

  return (
    <div className="flex flex-col gap-5 p-4">
      <div>
        <h3 className="text-lg font-bold text-[var(--foreground)]">
          <BookOpen size={15} className="inline mr-1 align-[-2px]" /> {current_topic}
        </h3>
        <div className="mt-1 flex items-center gap-3 text-sm text-[var(--muted-foreground)]">
          <span>{nodes.length} 个节点</span>
          {estimated_hours && (
            <span className="flex items-center gap-1">
              <Clock size={14} /> 约 {estimated_hours} 小时
            </span>
          )}
        </div>
      </div>

      {/* 按类型分组展示 */}
      <div className="flex flex-col gap-4">
        {order.map((type) => {
          const items = grouped[type];
          if (!items || items.length === 0) return null;
          const cfg = TYPE_CONFIG[type] ?? { label: type, color: "", icon: BookOpen };
          return (
            <div key={type}>
              <Badge className={cn("mb-2 text-xs", cfg.color)}>{cfg.label}</Badge>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {items.map((node) => (
                  <div
                    key={node.id}
                    className="rounded-lg border border-gray-200 p-3 dark:border-gray-700"
                  >
                    <p className="text-sm font-semibold text-[var(--foreground)]">
                      {node.name}
                    </p>
                    <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                      {node.description}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* 依赖关系 */}
      {data.edges.length > 0 && (
        <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
          <p className="text-xs font-medium text-gray-500 mb-2">依赖关系</p>
          <div className="flex flex-wrap gap-2">
            {data.edges.map((edge, i) => {
              const src = nodes.find((n) => n.id === edge.source);
              const tgt = nodes.find((n) => n.id === edge.target);
              return (
                <span key={i} className="inline-flex items-center gap-1 text-xs text-[var(--foreground)]/80">
                  {src?.name ?? edge.source}
                  <ArrowRight size={12} />
                  {tgt?.name ?? edge.target}
                  <span className="text-[var(--muted-foreground)]">({edge.relation})</span>
                </span>
              );
            })}
          </div>
        </div>
      )}

      {/* 学习建议 */}
      {learning_tips && learning_tips.length > 0 && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 dark:border-blue-800 dark:bg-blue-950">
          <p className="flex items-center gap-1 text-sm font-semibold text-[var(--interactive)] mb-2"><Lightbulb size={14} /> 学习建议</p>
          <ul className="list-inside list-disc space-y-1 text-sm text-[var(--interactive)]">
            {learning_tips.map((tip, i) => (
              <li key={i}>{tip}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
