import { memo, useEffect, useMemo, useRef, useState } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  ReactFlow,
  type Edge,
  type Node,
  type ReactFlowInstance,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { DSLVisualObject } from "../simulation-model";

type GraphNodeInput = {
  id?: string;
  label?: string;
  value?: unknown;
  position?: { x?: number; y?: number };
};

type GraphEdgeInput = {
  id?: string;
  source?: string;
  target?: string;
  label?: string;
  weight?: string | number;
  directed?: boolean;
};

const toRecordArray = <T,>(value: unknown): T[] =>
  Array.isArray(value) ? (value as T[]) : [];

function makePosition(index: number, count: number, isTree: boolean) {
  if (isTree) {
    const level = Math.floor(Math.log2(index + 1));
    const firstAtLevel = 2 ** level - 1;
    const indexAtLevel = index - firstAtLevel;
    const nodesAtLevel = 2 ** level;
    return {
      x: ((indexAtLevel + 1) * 560) / (nodesAtLevel + 1),
      y: 24 + level * 96,
    };
  }

  const angle = (index / Math.max(count, 1)) * Math.PI * 2 - Math.PI / 2;
  return { x: 250 + Math.cos(angle) * 190, y: 145 + Math.sin(angle) * 125 };
}

export const StructureGraphObject = memo(function StructureGraphObject({
  object,
  interactionMode = "browse",
  selectedNodeId,
  onNodeSelect,
  className,
}: {
  object: DSLVisualObject;
  interactionMode?: "browse" | "edit";
  selectedNodeId?: string;
  onNodeSelect?: (nodeId: string) => void;
  className?: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [flow, setFlow] = useState<ReactFlowInstance | null>(null);
  const isTree = object.type === "tree";

  const inputNodes = useMemo(
    () => toRecordArray<GraphNodeInput>(object.nodes ?? object.children),
    [object.children, object.nodes],
  );
  const inputEdges = useMemo(
    () => toRecordArray<GraphEdgeInput>(object.graph_edges ?? object.edges),
    [object.edges, object.graph_edges],
  );

  const nodes = useMemo<Node[]>(
    () =>
      inputNodes.map((node, index) => {
        const id = String(node.id ?? node.label ?? index + 1);
        const fallback = makePosition(index, inputNodes.length, isTree);
        return {
          id,
          selected: selectedNodeId === id,
          position: {
            x: Number(node.position?.x ?? fallback.x),
            y: Number(node.position?.y ?? fallback.y),
          },
          data: { label: String(node.label ?? node.value ?? id) },
          draggable: false,
          selectable: true,
          style: {
            minWidth: 46,
            borderRadius: isTree ? 8 : 999,
            border: selectedNodeId === id
              ? "3px solid var(--interactive)"
              : "2px solid var(--graph-active)",
            background: selectedNodeId === id
              ? "color-mix(in oklch, var(--interactive) 14%, var(--card))"
              : "var(--card)",
            color: "var(--foreground)",
            fontSize: 12,
            fontWeight: 700,
            padding: "7px 10px",
            boxShadow: selectedNodeId === id
              ? "0 0 0 7px color-mix(in oklch, var(--interactive) 12%, transparent)"
              : undefined,
            cursor: interactionMode === "edit" ? "move" : "pointer",
          },
        };
      }),
    [inputNodes, interactionMode, isTree, selectedNodeId],
  );

  const edges = useMemo<Edge[]>(
    () =>
      inputEdges
        .filter((edge) => edge.source != null && edge.target != null)
        .map((edge, index) => ({
          id: String(edge.id ?? `edge-${index}`),
          source: String(edge.source),
          target: String(edge.target),
          label: edge.label ?? edge.weight,
          type: isTree ? "smoothstep" : "straight",
          markerEnd: edge.directed === false ? undefined : { type: "arrowclosed" as const },
          selectable: false,
          focusable: false,
          style: { stroke: "var(--graph-line)", strokeWidth: 2 },
          labelStyle: { fill: "var(--muted-foreground)", fontSize: 11, fontWeight: 600 },
          labelBgStyle: { fill: "var(--card)", fillOpacity: 0.95 },
        })),
    [inputEdges, isTree],
  );

  useEffect(() => {
    if (!flow || !containerRef.current) return;
    const fit = () => void flow.fitView({ padding: 0.2, duration: 0, maxZoom: 1.15 });
    const observer = new ResizeObserver(fit);
    observer.observe(containerRef.current);
    fit();
    return () => observer.disconnect();
  }, [flow, nodes.length, edges.length]);

  if (nodes.length === 0) {
    return (
      <div className={className}>
        <p className="text-xs text-muted-foreground">{object.label ?? "结构图"}暂无节点数据</p>
      </div>
    );
  }

  return (
    <div ref={containerRef} className={className ?? "h-72 w-full"}>
      <ReactFlow
        aria-label={String(object.label ?? (isTree ? "树结构" : "图结构"))}
        nodes={nodes}
        edges={edges}
        onInit={setFlow}
        onNodeClick={(event, node) => {
          event.stopPropagation();
          onNodeSelect?.(node.id);
        }}
        onNodeDoubleClick={(event, node) => {
          event.stopPropagation();
          onNodeSelect?.(node.id);
          void flow?.fitView({ nodes: [node], padding: 1.6, duration: 280, maxZoom: 1.45 });
        }}
        onPaneClick={(event) => {
          event.stopPropagation();
          onNodeSelect?.("");
        }}
        fitView
        fitViewOptions={{ padding: 0.2, maxZoom: 1.15 }}
        nodesDraggable={interactionMode === "edit"}
        nodesConnectable={false}
        elementsSelectable
        panOnDrag
        zoomOnScroll={false}
        zoomOnPinch
        zoomOnDoubleClick={false}
        zoomActivationKeyCode="Control"
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={18} size={1} color="var(--stage-dot)" />
        <Controls showInteractive={false} position="bottom-right" />
      </ReactFlow>
    </div>
  );
});

export default StructureGraphObject;
