/**
 * 知识卡片组件（KnowledgeCard）。
 *
 * 展示知识概念卡片：定义、直观解释、常见误区、公式或伪代码、相关帧。
 * 在播放器侧边展示，可点击跳转到相关帧。
 *
 * 对齐：需求文档 10.5 节 + 设计文档 7.1.1 节。
 */

import { memo } from "react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { BookOpen, AlertTriangle, Link2, Lightbulb } from "lucide-react";

export type KnowledgeCardData = {
  id: string;
  title: string;
  definition?: string;
  intuition?: string;
  pitfalls?: string[];
  formula?: string;
  pseudocode?: string;
  relatedFrameIds?: string[];
  category?: string;
  difficulty?: number;
};

export type KnowledgeCardProps = {
  card: KnowledgeCardData;
  onFrameClick?: (frameId: string) => void;
  className?: string;
};

export const KnowledgeCard = memo(function KnowledgeCard({
  card,
  onFrameClick,
  className,
}: KnowledgeCardProps) {
  return (
    <div
      className={cn(
        "rounded-xl border bg-card p-4 shadow-sm transition-shadow hover:shadow-md",
        className,
      )}
    >
      {/* 头部 */}
      <div className="flex items-start justify-between gap-2 mb-3">
        <h4 className="font-semibold text-sm flex items-center gap-1.5">
          <BookOpen size={14} className="text-primary shrink-0" />
          {card.title}
        </h4>
        {card.category && (
          <Badge variant="secondary" className="text-[10px] shrink-0">
            {card.category}
          </Badge>
        )}
      </div>

      {/* 定义 */}
      {card.definition && (
        <p className="text-sm text-muted-foreground mb-3 leading-relaxed">
          {card.definition}
        </p>
      )}

      {/* 直观解释 */}
      {card.intuition && (
        <div className="mb-3 rounded-lg bg-muted/40 p-2.5">
          <p className="text-xs font-medium text-muted-foreground mb-1 flex items-center gap-1">
            <Lightbulb size={12} />
            直观理解
          </p>
          <p className="text-sm">{card.intuition}</p>
        </div>
      )}

      {/* 公式/伪代码 */}
      {card.formula && (
        <div className="mb-3 rounded-lg border bg-muted/20 p-2.5">
          <p className="text-xs font-medium text-muted-foreground mb-1">公式</p>
          <code className="text-sm font-mono">{card.formula}</code>
        </div>
      )}
      {card.pseudocode && (
        <div className="mb-3 rounded-lg border bg-[#0d1117] p-2.5">
          <p className="text-xs font-medium text-white/40 mb-1">伪代码</p>
          <pre className="text-sm font-mono text-white/85 whitespace-pre-wrap">
            {card.pseudocode}
          </pre>
        </div>
      )}

      {/* 常见误区 */}
      {card.pitfalls && card.pitfalls.length > 0 && (
        <div className="mb-3">
          <p className="text-xs font-medium text-muted-foreground mb-1.5 flex items-center gap-1">
            <AlertTriangle size={12} className="text-amber-500" />
            常见误区
          </p>
          <ul className="space-y-1">
            {card.pitfalls.map((p, idx) => (
              <li key={idx} className="text-xs text-muted-foreground flex gap-1.5">
                <span className="text-amber-500 shrink-0 mt-0.5">•</span>
                {p}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 相关帧 */}
      {card.relatedFrameIds && card.relatedFrameIds.length > 0 && (
        <div className="pt-2 border-t">
          <p className="text-xs font-medium text-muted-foreground mb-1.5 flex items-center gap-1">
            <Link2 size={12} />
            相关帧
          </p>
          <div className="flex flex-wrap gap-1">
            {card.relatedFrameIds.map((fid) => (
              <Button
                key={fid}
                variant="outline"
                size="sm"
                className="h-6 px-2 text-xs"
                onClick={() => onFrameClick?.(fid)}
              >
                {fid}
              </Button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
});

export default KnowledgeCard;