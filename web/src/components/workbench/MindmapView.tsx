/**
 * 思维导图画布。
 *
 * 节点位置由概念树计算，并支持分支收起、搜索、平移、缩放和推演帧跳转。
 */

import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
  type ReactFlowInstance,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { ChevronDown, ChevronRight, Focus, Network, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type MindmapNode = {
  id: string;
  name: string;
  type?: string;
  children?: MindmapNode[];
  relatedFrameIds?: string[];
};

export type MindmapViewProps = {
  root: MindmapNode;
  onNodeClick?: (nodeId: string) => void;
  onFrameClick?: (frameId: string) => void;
  className?: string;
};

const TYPE_LABELS: Record<string, string> = {
  definition: "定义",
  core_mechanism: "核心机制",
  prerequisite: "前置知识",
  comparison: "对比",
  extension: "延伸",
};

type MindmapNodeData = {
  source: MindmapNode;
  depth: number;
  matched: boolean;
  collapsed: boolean;
  onToggle: (nodeId: string) => void;
  onFrameClick?: (frameId: string) => void;
};

type MindmapFlowNode = Node<MindmapNodeData, "mindmap">;

const MindmapFlowNode = memo(function MindmapFlowNode({ data, selected }: NodeProps<MindmapFlowNode>) {
  const { source, depth, matched, collapsed, onToggle, onFrameClick } = data;
  const hasChildren = Boolean(source.children?.length);
  return (
    <article
      className={cn(
        "mindmap-flow-node min-w-44 max-w-60 rounded-lg border bg-[var(--card)] px-3 py-2.5 shadow-sm",
        selected && "is-selected",
        matched && "is-matched",
        depth === 0 && "is-root",
      )}
      data-node-type={source.type ?? "definition"}
    >
      {depth > 0 && (
        <Handle
          type="target"
          position={Position.Left}
          className="mindmap-flow-node__handle"
          aria-hidden="true"
        />
      )}
      <div className="flex items-start gap-2">
        <span className="mindmap-flow-node__marker mt-1.5 size-2 shrink-0 rounded-full" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold leading-5">{source.name}</p>
          <p className="mt-0.5 text-[9px] text-[var(--muted-foreground)]">
            {TYPE_LABELS[source.type ?? "definition"] ?? source.type ?? "概念"}
          </p>
        </div>
        {hasChildren && (
          <button
            type="button"
            className="nodrag nopan -mr-1 inline-flex size-7 shrink-0 items-center justify-center rounded-md text-[var(--muted-foreground)] transition-colors hover:bg-[var(--secondary)] hover:text-[var(--foreground)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--interactive)]"
            aria-label={`${collapsed ? "展开" : "收起"}分支：${source.name}`}
            aria-expanded={!collapsed}
            onClick={(event) => {
              event.stopPropagation();
              onToggle(source.id);
            }}
          >
            {collapsed ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
          </button>
        )}
      </div>
      {source.relatedFrameIds && source.relatedFrameIds.length > 0 && (
        <div className="nodrag nopan mt-2 flex flex-wrap gap-1 border-t border-[var(--border)] pt-2">
          {source.relatedFrameIds.map((frameId) => (
            <button
              key={frameId}
              type="button"
              className="rounded bg-[var(--secondary)] px-1.5 py-1 font-mono text-[9px] text-[var(--interactive)] transition-colors hover:bg-[color-mix(in_oklch,var(--interactive)_15%,var(--secondary))] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--interactive)]"
              aria-label={`跳转到推演帧 ${frameId}`}
              onClick={(event) => {
                event.stopPropagation();
                onFrameClick?.(frameId);
              }}
            >
              {frameId}
            </button>
          ))}
        </div>
      )}
      {hasChildren && (
        <Handle
          type="source"
          position={Position.Right}
          className="mindmap-flow-node__handle"
          aria-hidden="true"
        />
      )}
    </article>
  );
});

const nodeTypes = { mindmap: MindmapFlowNode };

function countNodes(node: MindmapNode): number {
  return 1 + (node.children ?? []).reduce((sum, child) => sum + countNodes(child), 0);
}

function collectBranchIds(node: MindmapNode, result = new Set<string>()) {
  if (node.children?.length) result.add(node.id);
  node.children?.forEach((child) => collectBranchIds(child, result));
  return result;
}

function layoutMindmap(
  root: MindmapNode,
  collapsedIds: Set<string>,
  query: string,
  onToggle: (nodeId: string) => void,
  onFrameClick?: (frameId: string) => void,
) {
  const nodes: MindmapFlowNode[] = [];
  const edges: Edge[] = [];
  let leafIndex = 0;
  const normalizedQuery = query.trim().toLocaleLowerCase();

  const visit = (node: MindmapNode, depth: number, parentId?: string): number => {
    const visibleChildren = collapsedIds.has(node.id) ? [] : (node.children ?? []);
    const childY = visibleChildren.map((child) => visit(child, depth + 1, node.id));
    const y = childY.length > 0
      ? childY.reduce((sum, value) => sum + value, 0) / childY.length
      : leafIndex++ * 112;

    nodes.push({
      id: node.id,
      type: "mindmap",
      position: { x: depth * 270, y },
      data: {
        source: node,
        depth,
        matched: Boolean(normalizedQuery && node.name.toLocaleLowerCase().includes(normalizedQuery)),
        collapsed: collapsedIds.has(node.id),
        onToggle,
        onFrameClick,
      },
      draggable: false,
      selectable: true,
    });

    if (parentId) {
      edges.push({
        id: `${parentId}-${node.id}`,
        source: parentId,
        target: node.id,
        type: "smoothstep",
        className: `mindmap-guide-edge mindmap-guide-edge--depth-${Math.min(depth, 3)}`,
        selectable: false,
        focusable: false,
        style: { stroke: "var(--graph-line)", strokeWidth: depth === 1 ? 2.5 : 1.75 },
      });
    }
    return y;
  };

  visit(root, 0);
  return { nodes, edges };
}

export const MindmapView = memo(function MindmapView({
  root,
  onNodeClick,
  onFrameClick,
  className,
}: MindmapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [flow, setFlow] = useState<ReactFlowInstance<MindmapFlowNode, Edge> | null>(null);
  const [collapsedIds, setCollapsedIds] = useState<Set<string>>(() => new Set());
  const [selectedId, setSelectedId] = useState<string>();
  const [query, setQuery] = useState("");

  const toggleBranch = useCallback((nodeId: string) => {
    setCollapsedIds((current) => {
      const next = new Set(current);
      if (next.has(nodeId)) next.delete(nodeId);
      else next.add(nodeId);
      return next;
    });
  }, []);

  const { nodes, edges } = useMemo(
    () => root
      ? layoutMindmap(root, collapsedIds, query, toggleBranch, onFrameClick)
      : { nodes: [], edges: [] },
    [collapsedIds, onFrameClick, query, root, toggleBranch],
  );
  const matchedNodes = nodes.filter((node) => node.data.matched);
  const selectedNode = nodes.find((node) => node.id === selectedId)?.data.source;
  const totalNodes = root ? countNodes(root) : 0;

  useEffect(() => {
    if (!flow || !containerRef.current) return;
    const fit = () => void flow.fitView({ padding: 0.16, duration: 0, maxZoom: 1.1 });
    const observer = new ResizeObserver(fit);
    observer.observe(containerRef.current);
    fit();
    return () => observer.disconnect();
  }, [flow, nodes]);

  const focusNode = (nodeId: string) => {
    const target = nodes.find((node) => node.id === nodeId);
    if (!target) return;
    setSelectedId(nodeId);
    onNodeClick?.(nodeId);
    void flow?.fitView({ nodes: [target], padding: 1.6, duration: 280, maxZoom: 1.35 });
  };

  if (!root) {
    return <p className={cn("p-6 text-sm text-[var(--muted-foreground)]", className)}>暂无可展示的概念导图</p>;
  }

  return (
    <section className={cn("overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--card)]", className)}>
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] px-3 py-3 sm:px-4">
        <div>
          <h3 className="flex items-center gap-2 text-sm font-semibold"><Network size={16} />概念导图</h3>
          <p className="mt-1 text-[10px] text-[var(--muted-foreground)]">{totalNodes} 个概念 · 拖动空白处平移 · 滚轮缩放</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="relative block">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)]" size={13} />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && matchedNodes[0]) focusNode(matchedNodes[0].id);
                if (event.key === "Escape") setQuery("");
              }}
              placeholder="搜索概念"
              aria-label="搜索思维导图概念"
              className="h-8 w-40 rounded-md border border-[var(--border)] bg-[var(--background)] pl-8 pr-7 text-xs outline-none focus:border-[var(--interactive)] focus:ring-2 focus:ring-[color-mix(in_oklch,var(--interactive)_15%,transparent)]"
            />
            {query && <span className="absolute right-2 top-1/2 -translate-y-1/2 font-mono text-[9px] text-[var(--muted-foreground)]">{matchedNodes.length}</span>}
          </label>
          <Button variant="outline" size="sm" onClick={() => {
            setCollapsedIds(new Set());
            window.setTimeout(() => void flow?.fitView({ padding: 0.16, duration: 280, maxZoom: 1.1 }), 0);
          }}>
            展开全部
          </Button>
          <Button variant="outline" size="sm" onClick={() => setCollapsedIds(collectBranchIds(root))}>
            收起分支
          </Button>
        </div>
      </header>

      <div className="grid min-h-[32rem] lg:grid-cols-[minmax(0,1fr)_15rem]">
        <div ref={containerRef} className="mindmap-canvas min-h-[32rem] bg-[var(--stage-bg)]">
          <ReactFlow
            aria-label="可交互思维导图"
            nodes={nodes.map((node) => ({ ...node, selected: node.id === selectedId }))}
            edges={edges}
            nodeTypes={nodeTypes}
            onInit={setFlow}
            onNodeClick={(_, node) => {
              setSelectedId(node.id);
              onNodeClick?.(node.id);
            }}
            onNodeDoubleClick={(_, node) => {
              if (node.data.source.children?.length) toggleBranch(node.id);
              else focusNode(node.id);
            }}
            onPaneClick={() => setSelectedId(undefined)}
            fitView
            fitViewOptions={{ padding: 0.16, maxZoom: 1.1 }}
            nodesDraggable={false}
            nodesConnectable={false}
            elementsSelectable
            panOnDrag
            zoomOnScroll
            zoomOnPinch
            zoomOnDoubleClick={false}
            minZoom={0.35}
            maxZoom={1.8}
            proOptions={{ hideAttribution: true }}
          >
            <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="var(--stage-dot)" />
            <Controls showInteractive={false} position="bottom-left" />
          </ReactFlow>
        </div>

        <aside className="border-t border-[var(--border)] bg-[var(--card)] p-4 lg:border-l lg:border-t-0">
          <p className="text-[10px] font-semibold text-[var(--muted-foreground)]">当前概念</p>
          {selectedNode ? (
            <div className="mt-3 space-y-3">
              <div>
                <p className="text-sm font-semibold leading-5">{selectedNode.name}</p>
                <p className="mt-1 text-[10px] text-[var(--muted-foreground)]">{TYPE_LABELS[selectedNode.type ?? "definition"] ?? selectedNode.type ?? "概念"}</p>
              </div>
              <dl className="space-y-2 border-y border-[var(--border)] py-3 text-xs">
                <div className="flex justify-between gap-3"><dt className="text-[var(--muted-foreground)]">子概念</dt><dd className="font-mono">{selectedNode.children?.length ?? 0}</dd></div>
                <div className="flex justify-between gap-3"><dt className="text-[var(--muted-foreground)]">关联帧</dt><dd className="font-mono">{selectedNode.relatedFrameIds?.length ?? 0}</dd></div>
              </dl>
              <Button variant="outline" size="sm" className="w-full" onClick={() => focusNode(selectedNode.id)}>
                <Focus />聚焦此概念
              </Button>
              {selectedNode.children && selectedNode.children.length > 0 && (
                <Button variant="outline" size="sm" className="w-full" onClick={() => toggleBranch(selectedNode.id)}>
                  {collapsedIds.has(selectedNode.id) ? <ChevronRight /> : <ChevronDown />}
                  {collapsedIds.has(selectedNode.id) ? "展开子概念" : "收起子概念"}
                </Button>
              )}
              {selectedNode.relatedFrameIds?.map((frameId) => (
                <Button key={frameId} variant="ghost" size="sm" className="w-full justify-between" onClick={() => onFrameClick?.(frameId)}>
                  跳转推演 <span className="font-mono">{frameId}</span>
                </Button>
              ))}
            </div>
          ) : (
            <p className="mt-3 text-xs leading-5 text-[var(--muted-foreground)]">单击节点查看层级和关联帧；双击分支节点可快速收起或展开。</p>
          )}
        </aside>
      </div>
    </section>
  );
});

export default MindmapView;
