/**
 * MisconceptionGallery — 常见误区展示面板。
 *
 * "错误→正确"翻转卡片效果，帮助纠正认知偏差。
 */

import { useState } from "react";
import { Lightbulb, AlertTriangle, ChevronDown, ChevronUp, XCircle, CheckCircle2, Paperclip } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

// ============================================================================
// 类型
// ============================================================================

export interface MisconceptionItem {
  id: string;
  concept: string;
  related_concept_id?: string;
  misconception: string;
  correction: string;
  counter_example?: string;
  why_it_matters?: string;
  difficulty: number;
}

export interface MisconceptionGalleryProps {
  items: MisconceptionItem[];
}

// ============================================================================
// 组件
// ============================================================================

const DIFFICULTY_LABELS: Record<number, string> = { 1: "初级", 2: "中级", 3: "高级" };

export function MisconceptionGallery({ items }: MisconceptionGalleryProps) {
  if (items.length === 0) {
    return <div className="p-8 text-center text-[var(--muted-foreground)]">暂无误区数据</div>;
  }

  return (
    <div className="flex flex-col gap-4 p-4">
      <div>
        <h3 className="text-lg font-bold text-[var(--foreground)]">常见误区</h3>
        <p className="text-sm text-[var(--muted-foreground)]">
          {items.length} 个常见误解，点击展开查看纠正
        </p>
      </div>

      <div className="flex flex-col gap-3">
        {items.map((item) => (
          <MisconceptionCard key={item.id} item={item} />
        ))}
      </div>
    </div>
  );
}

function MisconceptionCard({ item }: { item: MisconceptionItem }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className={cn(
        "rounded-lg border transition-all",
        expanded
          ? "border-green-200 bg-green-50/50 dark:border-green-800 dark:bg-green-950/50"
          : "border-red-200 bg-red-50/50 dark:border-red-800 dark:bg-red-950/50",
      )}
    >
      {/* 误区头部（始终可见） */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-start gap-3 p-4 text-left"
      >
        <AlertTriangle
          size={18}
          className={cn(
            "mt-0.5 shrink-0",
            expanded ? "text-[var(--success)]" : "text-[var(--error)]",
          )}
        />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-[var(--foreground)]">
              {item.concept}
            </span>
            <Badge className="text-xs">
              {DIFFICULTY_LABELS[item.difficulty] ?? item.difficulty}
            </Badge>
          </div>
          <p className={cn(
            "mt-1 text-sm line-through decoration-[var(--error)]",
            expanded ? "text-[var(--muted-foreground)]" : "text-[var(--error)]",
          )}>
            <XCircle size={14} className="inline mr-1 align-[-2px]" aria-label="误区" /> {item.misconception}
          </p>
        </div>
        {expanded ? <ChevronUp size={16} className="shrink-0 text-[var(--muted-foreground)]" />
                  : <ChevronDown size={16} className="shrink-0 text-[var(--muted-foreground)]" />}
      </button>

      {/* 纠正内容（展开后可见） */}
      {expanded && (
        <div className="border-t border-[var(--success)]/30 px-4 pb-4 pt-3 space-y-3">
          <div>
            <p className="flex items-center gap-1 text-xs font-medium text-[var(--success)]">
              <Lightbulb size={14} /> 正确理解
            </p>
            <p className="mt-1 text-sm text-[var(--success)]">
              <CheckCircle2 size={14} className="inline mr-1 align-[-2px]" aria-label="纠正" /> {item.correction}
            </p>
          </div>

          {item.counter_example && (
            <div>
              <p className="flex items-center gap-1 text-xs font-medium text-gray-500"><Paperclip size={12} /> 反例说明</p>
              <p className="mt-1 text-sm text-[var(--foreground)]/80">
                {item.counter_example}
              </p>
            </div>
          )}

          {item.why_it_matters && (
            <div>
              <p className="flex items-center gap-1 text-xs font-medium text-gray-500"><Lightbulb size={12} /> 为什么重要</p>
              <p className="mt-1 text-sm text-[var(--foreground)]/80">
                {item.why_it_matters}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
