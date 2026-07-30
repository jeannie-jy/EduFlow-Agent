/**
 * LearningPathway 组件测试。
 */

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { LearningPathway, type PathwayData } from "./LearningPathway";

function makeData(overrides: Partial<PathwayData> = {}): PathwayData {
  return {
    current_topic: "Dijkstra 最短路径",
    nodes: [
      { id: "n1", name: "图的表示", type: "prerequisite", description: "邻接表/矩阵" },
      { id: "n2", name: "贪心算法", type: "prerequisite", description: "局部最优" },
      { id: "n3", name: "Dijkstra", type: "core", description: "最短路径算法" },
      { id: "n4", name: "Bellman-Ford", type: "extension", description: "支持负权" },
      { id: "n5", name: "A* 搜索", type: "extension", description: "启发式搜索" },
      { id: "n6", name: "最小生成树", type: "related", description: "图论另一个主题" },
      { id: "n7", name: "OSPF 协议", type: "application", description: "网络路由" },
    ],
    edges: [
      { source: "n1", target: "n3", relation: "depends_on" },
      { source: "n2", target: "n3", relation: "depends_on" },
      { source: "n3", target: "n4", relation: "extends" },
      { source: "n3", target: "n5", relation: "extends" },
    ],
    estimated_hours: 3,
    learning_tips: ["先手写图的邻接表", "对比 BFS 和 Dijkstra"],
    ...overrides,
  };
}

describe("LearningPathway", () => {
  it("renders empty state", () => {
    render(<LearningPathway data={makeData({ nodes: [] })} />);
    expect(screen.getByText("暂无学习路径数据")).toBeInTheDocument();
  });

  it("renders topic title", () => {
    render(<LearningPathway data={makeData()} />);
    expect(screen.getByText(/Dijkstra 最短路径/)).toBeInTheDocument();
  });

  it("shows node count and estimated hours", () => {
    render(<LearningPathway data={makeData()} />);
    expect(screen.getByText(/7 个节点/)).toBeInTheDocument();
    expect(screen.getByText(/约 3 小时/)).toBeInTheDocument();
  });

  it("renders node names in all groups", () => {
    render(<LearningPathway data={makeData()} />);
    expect(screen.getByText("图的表示")).toBeInTheDocument();
    expect(screen.getByText("Dijkstra")).toBeInTheDocument();
    expect(screen.getByText("Bellman-Ford")).toBeInTheDocument();
    expect(screen.getByText("最小生成树")).toBeInTheDocument();
    expect(screen.getByText("OSPF 协议")).toBeInTheDocument();
  });

  it("renders group badges", () => {
    render(<LearningPathway data={makeData()} />);
    expect(screen.getByText("前置")).toBeInTheDocument();
    expect(screen.getByText("核心")).toBeInTheDocument();
    expect(screen.getByText("进阶")).toBeInTheDocument();
    expect(screen.getByText("相关")).toBeInTheDocument();
    expect(screen.getByText("应用")).toBeInTheDocument();
  });

  it("renders dependency edges", () => {
    render(<LearningPathway data={makeData()} />);
    const dependsOnElements = screen.getAllByText(/depends_on/);
    const extendsElements = screen.getAllByText(/extends/);
    expect(dependsOnElements.length).toBeGreaterThanOrEqual(2);
    expect(extendsElements.length).toBeGreaterThanOrEqual(2);
  });

  it("renders learning tips", () => {
    render(<LearningPathway data={makeData()} />);
    expect(screen.getByText(/学习建议/)).toBeInTheDocument();
    expect(screen.getByText("先手写图的邻接表")).toBeInTheDocument();
    expect(screen.getByText("对比 BFS 和 Dijkstra")).toBeInTheDocument();
  });

  it("hides tips section when empty", () => {
    render(<LearningPathway data={makeData({ learning_tips: [] })} />);
    expect(screen.queryByText("学习建议")).toBeNull();
  });

  it("hides hours when not provided", () => {
    render(<LearningPathway data={makeData({ estimated_hours: undefined })} />);
    expect(screen.queryByText(/小时/)).toBeNull();
  });

  it("renders node descriptions", () => {
    render(<LearningPathway data={makeData()} />);
    expect(screen.getByText("邻接表/矩阵")).toBeInTheDocument();
    expect(screen.getByText("最短路径算法")).toBeInTheDocument();
    expect(screen.getByText("支持负权")).toBeInTheDocument();
  });
});
