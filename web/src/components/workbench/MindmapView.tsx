/**
 * 思维导图组件（MindmapView）。
 *
 * 根据概念关系渲染树形思维导图，支持从节点跳转到推演帧。
 *
 * 对齐：需求文档 10.6 节 + 设计文档 7.1.4 节。
 */

import { memo } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ChevronRight, Circle } from "lucide-react";

export type MindmapNode = {
  id: string;
  name: string;
  type?: string;          // definition / core_mechanism / prerequisite / comparison / extension
  children?: MindmapNode[];
  relatedFrameIds?: string[];
};

export type MindmapViewProps = {
  root: MindmapNode;
  onNodeClick?: (nodeId: string) => void;
  onFrameClick?: (frameId: string) => void;
  className?: string;
};

/** 节点类型对应的颜色 */
const TYPE_COLORS: Record<string, string> = {
  definition: "text-blue-600 border-blue-200 bg-blue-50",
  core_mechanism: "text-green-600 border-green-200 bg-green-50",
  prerequisite: "text-slate-500 border-slate-200 bg-slate-50",
  comparison: "text-amber-600 border-amber-200 bg-amber-50",
  extension: "text-purple-600 border-purple-200 bg-purple-50",
};

const TYPE_ICON_COLORS: Record<string, string> = {
  definition: "fill-blue-500",
  core_mechanism: "fill-green-500",
  prerequisite: "fill-slate-400",
  comparison: "fill-amber-500",
  extension: "fill-purple-500",
};

function MindmapTreeNode({
  node,
  depth = 0,
  onNodeClick,
  onFrameClick,
}: {
  node: MindmapNode;
  depth: number;
  onNodeClick?: (nodeId: string) => void;
  onFrameClick?: (frameId: string) => void;
}) {
  const colors = TYPE_COLORS[node.type ?? "definition"] ?? TYPE_COLORS.definition;
  const iconColor = TYPE_ICON_COLORS[node.type ?? "definition"] ?? TYPE_ICON_COLORS.definition;
  const maxDepth = 4;
  const clampedDepth = Math.min(depth, maxDepth);

  return (
    <div className={cn(depth > 0 && "ml-5 border-l-2 border-muted pl-4")}>
      {/* 节点 */}
      <div
        className={cn(
          "inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 cursor-pointer",
          "transition-colors hover:shadow-sm",
          colors,
        )}
        onClick={() => onNodeClick?.(node.id)}
        role="button"
        tabIndex={0}
        aria-label={`概念: ${node.name}`}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onNodeClick?.(node.id);
          }
        }}
      >
        <Circle size={8} className={iconColor} />
        <span className="text-sm font-medium">{node.name}</span>
        {node.type && (
          <span className="text-[10px] opacity-60">{node.type}</span>
        )}
      </div>

      {/* 关联帧 */}
      {node.relatedFrameIds && node.relatedFrameIds.length > 0 && (
        <div className="mt-1 ml-1 flex flex-wrap gap-1">
          {node.relatedFrameIds.map((fid) => (
            <Button
              key={fid}
              variant="ghost"
              size="sm"
              className="h-5 px-1.5 text-[10px] text-muted-foreground"
              onClick={(e) => {
                e.stopPropagation();
                onFrameClick?.(fid);
              }}
            >
              <ChevronRight size={10} />
              {fid}
            </Button>
          ))}
        </div>
      )}

      {/* 子节点 */}
      {node.children?.map((child) => (
        <MindmapTreeNode
          key={child.id}
          node={child}
          depth={clampedDepth + 1}
          onNodeClick={onNodeClick}
          onFrameClick={onFrameClick}
        />
      ))}
    </div>
  );
}

export const MindmapView = memo(function MindmapView({
  root,
  onNodeClick,
  onFrameClick,
  className,
}: MindmapViewProps) {
  return (
    <div className={cn("space-y-2 p-4", className)}>
      <h3 className="text-sm font-semibold mb-4">概念导图</h3>
      <MindmapTreeNode
        node={root}
        depth={0}
        onNodeClick={onNodeClick}
        onFrameClick={onFrameClick}
      />
    </div>
  );
});

export default MindmapView;