import { describe, expect, it } from "vitest";
import { buildDijkstraFrames, buildDijkstraScenario } from "./simulation-model";

describe("Dijkstra simulation model", () => {
  it("produces fourteen coherent teaching frames", () => {
    const frames = buildDijkstraFrames();

    expect(frames).toHaveLength(14);
    expect(frames.map((frame) => frame.id)).toEqual(
      Array.from({ length: 14 }, (_, index) => index + 1),
    );
    expect(frames.at(-1)?.phase).toBe("complete");
  });

  it("computes a consistent shortest-path result from source A", () => {
    const finalFrame = buildDijkstraFrames().at(-1);

    expect(finalFrame?.distances).toEqual({ A: 0, B: 2, C: 3, D: 9, E: 5, F: 7 });
    expect(finalFrame?.predecessors).toEqual({ A: null, B: "A", C: "A", D: "B", E: "A", F: "C" });
    expect(finalFrame?.settledNodes).toEqual(["A", "B", "C", "E", "F", "D"]);
  });

  it("keeps narration, changed edges and distance snapshots synchronized", () => {
    const cRelaxFrame = buildDijkstraFrames()[7];

    expect(cRelaxFrame.currentNode).toBe("C");
    expect(cRelaxFrame.changedEdges).toEqual(["C-F"]);
    expect(cRelaxFrame.distances.F).toBe(7);
    expect(cRelaxFrame.predecessors.F).toBe("C");
    expect(cRelaxFrame.narration).toContain("F 更新为 7");
    expect(cRelaxFrame.narration).toContain("D 保持 9");
    expect(cRelaxFrame.narration).toContain("E 保持 5");
  });

  it("recomputes frames and graph labels after changing B-D weight", () => {
    const scenario = buildDijkstraScenario({ edgeOverrides: { "B-D": 3 } });
    expect(scenario.edges.find((edge) => edge.id === "B-D")?.weight).toBe(3);
    expect(scenario.frames.at(-1)?.distances.D).toBe(5);
    expect(scenario.frames.at(-1)?.predecessors.D).toBe("B");
  });

  it("does not mutate the default scenario", () => {
    const changed = buildDijkstraScenario({ edgeOverrides: { "B-D": 3 } });
    const original = buildDijkstraScenario();
    expect(changed.edges).not.toBe(original.edges);
    expect(original.edges.find((edge) => edge.id === "B-D")?.weight).toBe(7);
    expect(original.frames.at(-1)?.distances.D).toBe(9);
  });
});
