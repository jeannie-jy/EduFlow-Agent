export const graphNodeIds = ["A", "B", "C", "D", "E", "F"] as const;

export type GraphNodeId = (typeof graphNodeIds)[number];

export type SimulationPhase = "configure" | "initialize" | "select" | "relax" | "complete";

export type GraphNodeSpec = {
  id: GraphNodeId;
  position: { x: number; y: number };
};

export type GraphEdgeSpec = {
  id: string;
  source: GraphNodeId;
  target: GraphNodeId;
  sourceHandle: "top" | "right" | "bottom" | "left";
  targetHandle: "top" | "right" | "bottom" | "left";
  weight: number;
};

export type SimulationFrame = {
  id: number;
  phase: SimulationPhase;
  title: string;
  currentNode: GraphNodeId;
  distances: Record<GraphNodeId, number>;
  predecessors: Record<GraphNodeId, GraphNodeId | null>;
  settledNodes: GraphNodeId[];
  inspectedEdges: string[];
  changedEdges: string[];
  narration: string;
};

export const graphNodes: GraphNodeSpec[] = [
  { id: "A", position: { x: 70, y: 250 } },
  { id: "B", position: { x: 340, y: 70 } },
  { id: "C", position: { x: 360, y: 270 } },
  { id: "D", position: { x: 760, y: 100 } },
  { id: "E", position: { x: 340, y: 500 } },
  { id: "F", position: { x: 710, y: 475 } },
];

export const graphEdges: GraphEdgeSpec[] = [
  { id: "A-B", source: "A", target: "B", sourceHandle: "right", targetHandle: "left", weight: 2 },
  { id: "A-C", source: "A", target: "C", sourceHandle: "right", targetHandle: "left", weight: 3 },
  { id: "A-E", source: "A", target: "E", sourceHandle: "bottom", targetHandle: "left", weight: 5 },
  { id: "B-C", source: "B", target: "C", sourceHandle: "bottom", targetHandle: "top", weight: 2 },
  { id: "B-D", source: "B", target: "D", sourceHandle: "right", targetHandle: "left", weight: 7 },
  { id: "C-D", source: "C", target: "D", sourceHandle: "right", targetHandle: "bottom", weight: 6 },
  { id: "C-E", source: "C", target: "E", sourceHandle: "bottom", targetHandle: "top", weight: 3 },
  { id: "C-F", source: "C", target: "F", sourceHandle: "right", targetHandle: "left", weight: 4 },
  { id: "E-F", source: "E", target: "F", sourceHandle: "right", targetHandle: "left", weight: 2 },
];

const createDistances = (): Record<GraphNodeId, number> => ({
  A: 0,
  B: Number.POSITIVE_INFINITY,
  C: Number.POSITIVE_INFINITY,
  D: Number.POSITIVE_INFINITY,
  E: Number.POSITIVE_INFINITY,
  F: Number.POSITIVE_INFINITY,
});

const createPredecessors = (): Record<GraphNodeId, GraphNodeId | null> => ({
  A: null,
  B: null,
  C: null,
  D: null,
  E: null,
  F: null,
});

const formatDistance = (distance: number) =>
  Number.isFinite(distance) ? String(distance) : "∞";

const buildAdjacency = () => {
  const adjacency = new Map<GraphNodeId, Array<{ edge: GraphEdgeSpec; neighbor: GraphNodeId }>>();
  graphNodeIds.forEach((node) => adjacency.set(node, []));
  graphEdges.forEach((edge) => {
    adjacency.get(edge.source)?.push({ edge, neighbor: edge.target });
    adjacency.get(edge.target)?.push({ edge, neighbor: edge.source });
  });
  return adjacency;
};

export function buildDijkstraFrames(): SimulationFrame[] {
  const adjacency = buildAdjacency();
  const distances = createDistances();
  const predecessors = createPredecessors();
  const settled = new Set<GraphNodeId>();
  const frames: SimulationFrame[] = [];

  const pushFrame = (
    phase: SimulationPhase,
    title: string,
    currentNode: GraphNodeId,
    inspectedEdges: string[],
    changedEdges: string[],
    narration: string,
  ) => {
    frames.push({
      id: frames.length + 1,
      phase,
      title,
      currentNode,
      distances: { ...distances },
      predecessors: { ...predecessors },
      settledNodes: [...settled],
      inspectedEdges,
      changedEdges,
      narration,
    });
  };

  pushFrame("configure", "设置源点", "A", [], [], "选择 A 作为源点，准备建立距离表与优先队列。");
  pushFrame("initialize", "初始化距离", "A", [], [], "将 A 的距离设为 0，其余节点暂记为 ∞。");

  while (settled.size < graphNodeIds.length) {
    const current = graphNodeIds
      .filter((node) => !settled.has(node))
      .sort((left, right) => distances[left] - distances[right])[0];

    pushFrame(
      "select",
      `选择节点 ${current}`,
      current,
      [],
      [],
      `未确定节点中，${current} 的暂定距离 ${formatDistance(distances[current])} 最小，因此选中 ${current}。`,
    );

    settled.add(current);

    if (settled.size === graphNodeIds.length) {
      pushFrame("complete", "推演完成", current, [], [], "全部节点均已确定，最短路径计算完成。");
      break;
    }

    const inspectedEdges: string[] = [];
    const changedEdges: string[] = [];
    const changes: string[] = [];
    const unchanged: string[] = [];

    for (const { edge, neighbor } of adjacency.get(current) ?? []) {
      if (settled.has(neighbor)) continue;
      inspectedEdges.push(edge.id);
      const candidate = distances[current] + edge.weight;
      if (candidate < distances[neighbor]) {
        distances[neighbor] = candidate;
        predecessors[neighbor] = current;
        changedEdges.push(edge.id);
        changes.push(`${neighbor} 更新为 ${candidate}`);
      } else {
        unchanged.push(`${neighbor} 保持 ${formatDistance(distances[neighbor])}`);
      }
    }

    pushFrame(
      "relax",
      `松弛 ${current} 的邻边`,
      current,
      inspectedEdges,
      changedEdges,
      [...changes, ...unchanged].length > 0
        ? `检查 ${current} 的未确定邻居：${[...changes, ...unchanged].join("，")}。`
        : `检查 ${current} 的未确定邻居，没有产生更短路径。`,
    );
  }

  return frames;
}

export const simulationFrames = buildDijkstraFrames();

export function getEdgeIdBetween(left: GraphNodeId, right: GraphNodeId) {
  return graphEdges.find(
    (edge) =>
      (edge.source === left && edge.target === right) ||
      (edge.source === right && edge.target === left),
  )?.id;
}

export function getDistanceLabel(distance: number) {
  return formatDistance(distance);
}
