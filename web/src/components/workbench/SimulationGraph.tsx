import { memo, useEffect, useMemo, useRef, useState } from "react";
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
import { cn } from "@/lib/utils";
import {
  getDistanceLabel,
  getEdgeIdBetween,
  graphEdges,
  graphNodes,
  type GraphEdgeSpec,
  type GraphNodeId,
  type SimulationFrame,
} from "./simulation-model";

type SimulationNodeData = {
  nodeId: GraphNodeId;
  distance: string;
  status: "current" | "settled" | "unvisited";
};

type SimulationFlowNode = Node<SimulationNodeData, "simulation">;

const handlePositions = {
  top: Position.Top,
  right: Position.Right,
  bottom: Position.Bottom,
  left: Position.Left,
} as const;

const SimulationNode = memo(function SimulationNode({ data }: NodeProps<SimulationFlowNode>) {
  return (
    <div
      className={cn(
        "simulation-flow-node",
        data.status === "current" && "is-current",
        data.status === "settled" && "is-settled",
      )}
      aria-label={`节点 ${data.nodeId}，${data.status === "current" ? "当前节点" : data.status === "settled" ? "已确定" : "未访问"}，距离 ${data.distance}`}
    >
      {Object.entries(handlePositions).map(([id, position]) => (
        <Handle key={`target-${id}`} id={id} type="target" position={position} />
      ))}
      <span className="simulation-flow-node__id">{data.nodeId}</span>
      <span className="simulation-flow-node__distance">{data.distance}</span>
      {Object.entries(handlePositions).map(([id, position]) => (
        <Handle key={`source-${id}`} id={id} type="source" position={position} />
      ))}
    </div>
  );
});

const nodeTypes = { simulation: SimulationNode };

type SimulationGraphProps = {
  frame: SimulationFrame;
  edges?: GraphEdgeSpec[];
  compact?: boolean;
  panActivationKeyCode?: string | null;
};

export function SimulationGraph({
  frame,
  edges: edgeSpecs = graphEdges,
  compact: compactOverride,
  panActivationKeyCode,
}: SimulationGraphProps) {
  const [viewportCompact, setViewportCompact] = useState(() => window.matchMedia("(max-width: 639px)").matches);
  const compact = compactOverride ?? viewportCompact;
  const [flow, setFlow] = useState<ReactFlowInstance<SimulationFlowNode, Edge> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const query = window.matchMedia("(max-width: 639px)");
    const handleChange = () => setViewportCompact(query.matches);
    query.addEventListener("change", handleChange);
    return () => query.removeEventListener("change", handleChange);
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    if (!flow || !container) return;

    let animationFrame = 0;
    const fitToContainer = () => {
      window.cancelAnimationFrame(animationFrame);
      animationFrame = window.requestAnimationFrame(() => {
        void flow.fitView({
          padding: compact ? 0.14 : 0.2,
          minZoom: compact ? 0.48 : 0.65,
          maxZoom: 1.05,
          duration: 0,
        });
      });
    };

    const observer = new ResizeObserver(fitToContainer);
    observer.observe(container);
    fitToContainer();

    return () => {
      window.cancelAnimationFrame(animationFrame);
      observer.disconnect();
    };
  }, [compact, flow, frame.id]);

  const treeEdges = useMemo(
    () =>
      new Set(
        Object.entries(frame.predecessors)
          .map(([node, predecessor]) =>
            predecessor &&
            frame.settledNodes.includes(node as GraphNodeId) &&
            frame.settledNodes.includes(predecessor)
              ? getEdgeIdBetween(node as GraphNodeId, predecessor)
              : undefined,
          )
          .filter((edge): edge is string => Boolean(edge)),
      ),
    [frame.predecessors, frame.settledNodes],
  );

  const nodes = useMemo<SimulationFlowNode[]>(
    () =>
      graphNodes.map((node) => ({
        id: node.id,
        type: "simulation",
        position: compact
          ? { x: node.position.x * 0.56, y: node.position.y * 0.58 }
          : node.position,
        draggable: false,
        selectable: false,
        data: {
          nodeId: node.id,
          distance: getDistanceLabel(frame.distances[node.id]),
          status:
            frame.currentNode === node.id
              ? "current"
              : frame.settledNodes.includes(node.id)
                ? "settled"
                : "unvisited",
        },
      })),
    [compact, frame],
  );

  const flowEdges = useMemo<Edge[]>(
    () =>
      edgeSpecs.map((edge) => {
        const changed = frame.changedEdges.includes(edge.id);
        const inspected = frame.inspectedEdges.includes(edge.id);
        const inTree = treeEdges.has(edge.id);

        return {
          id: edge.id,
          source: edge.source,
          target: edge.target,
          sourceHandle: edge.sourceHandle,
          targetHandle: edge.targetHandle,
          type: "straight",
          label: edge.weight,
          animated: changed,
          selectable: false,
          focusable: false,
          className: cn(
            "simulation-flow-edge",
            inTree && "is-tree",
            inspected && "is-inspected",
            changed && "is-changed",
          ),
          labelStyle: { fill: "var(--muted-foreground)", fontSize: 12, fontWeight: 600 },
          labelBgStyle: { fill: "var(--card)", fillOpacity: 0.94 },
          labelBgPadding: [5, 3] as [number, number],
          labelBgBorderRadius: 5,
        };
      }),
    [edgeSpecs, frame.changedEdges, frame.inspectedEdges, treeEdges],
  );

  return (
    <>
      <ul className="sr-only" aria-label="图边列表">
        {edgeSpecs.map((edge) => (
          <li key={edge.id} aria-label={`边 ${edge.source} 到 ${edge.target}，权重 ${edge.weight}`}>
            {edge.source} 到 {edge.target}，权重 {edge.weight}
          </li>
        ))}
      </ul>
      <div ref={containerRef} className="size-full">
        <ReactFlow
          aria-label="Dijkstra 六节点交互图"
          nodes={nodes}
          edges={flowEdges}
          nodeTypes={nodeTypes}
          onInit={setFlow}
          fitView
          fitViewOptions={{ padding: compact ? 0.14 : 0.2, minZoom: compact ? 0.48 : 0.65, maxZoom: 1.05 }}
          minZoom={compact ? 0.4 : 0.55}
          maxZoom={1.35}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          panActivationKeyCode={panActivationKeyCode}
          panOnScroll
          zoomOnDoubleClick={false}
          proOptions={{ hideAttribution: true }}
        >
          <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="var(--stage-dot)" />
          <Controls showInteractive={false} position="bottom-right" />
        </ReactFlow>
      </div>
    </>
  );
}
