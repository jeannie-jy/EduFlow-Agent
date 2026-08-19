import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ProjectDetailResponse } from "@/services/projects";
import { ModuleResultsPanel } from "./ModuleResultsPanel";

const frames = {
  schema_version: "1.0",
  artifact_version: "cross-module-v1",
  frames: [
    {
      frame_id: "f_001",
      title: "建立初始状态",
      narration: "准备开始。",
      visual_objects: [],
      state_snapshot: {},
      checks: [],
    },
    {
      frame_id: "f_002",
      title: "执行松弛操作",
      narration: "更新更短距离。",
      visual_objects: [],
      state_snapshot: {},
      checks: [],
    },
  ],
};

function projectWith(moduleOutputs: Record<string, unknown>) {
  return {
    id: "project-cross-module",
    title: "跨模块导航",
    status: "done",
    module_outputs: moduleOutputs,
    updated_at: "2026-08-13T00:00:00Z",
  } as unknown as ProjectDetailResponse;
}

describe("ModuleResultsPanel cross-module navigation", () => {
  it("exposes every distinct artifact workspace for a non-algorithm user topic", () => {
    const project = projectWith({
      mindmap: { root: { id: "tcp", name: "TCP 三次握手", children: [] } },
      cards: { cards: [{ id: "syn", title: "SYN", definition: "客户端发起连接", intuition: "请求建立会话", pitfalls: [] }] },
      frames,
      quiz: { questions: [] },
      comparison: { topic: "连接建立方式", algorithms: [], dimensions: [], comparison_table: [], scenario_analysis: "" },
      misconception: { items: [] },
      pathway: { current_topic: "TCP 三次握手", nodes: [], edges: [], learning_tips: [] },
      sandbox: { language: "python", starter_code: "# TCP state machine", full_solution: "# solution", test_cases: [] },
      interactive_demo: { code: "const InteractiveDemo = () => <div>TCP handshake</div>;" },
      video: { status: "idle", config: {} },
    });
    project.title = "TCP 三次握手";

    render(<ModuleResultsPanel project={project} />);

    expect(screen.getByText("9 个已生成")).toBeInTheDocument();
    for (const name of ["思维导图", "知识卡片", "交互推演", "小练习", "对比分析", "常见误区", "学习路径", "代码沙箱", "教学视频"]) {
      expect(screen.getByRole("button", { name: new RegExp(name) })).toBeInTheDocument();
    }
  });

  it("keeps selected failed modules visible with their error", () => {
    const project = projectWith({ video: { status: "failed" } });
    project.selected_modules = ["frames", "quiz", "video"];
    project.dsl = { module_errors: { frames: "Insufficient Balance", quiz: "Insufficient Balance" } };

    render(<ModuleResultsPanel project={project} />);

    expect(screen.getByText("1 个已生成 · 1 个失败")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /小练习/ }));
    expect(screen.getByText("智能生成额度不足")).toBeInTheDocument();
    expect(screen.queryByText("Insufficient Balance")).not.toBeInTheDocument();
  });

  it("keeps internal video frames out of result navigation", () => {
    render(<ModuleResultsPanel project={projectWith({ frames })} />);

    expect(screen.queryByRole("button", { name: /推演脚本|交互推演/ })).not.toBeInTheDocument();
  });

  it("uses the generated interactive demo even for Dijkstra", async () => {
    const project = projectWith({
      interactive_demo: {
        code: "const InteractiveDemo = () => <div>Dijkstra shortest path</div>;",
      },
    });
    project.title = "Dijkstra 最短路径";

    render(<ModuleResultsPanel project={project} />);

    expect(await screen.findByTitle("交互推演", undefined, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.queryByLabelText("Dijkstra 最短路径互动演示")).not.toBeInTheDocument();
  });

  it("jumps from a knowledge card to its related frame", async () => {
    render(<ModuleResultsPanel project={projectWith({
      frames,
      video: { status: "idle", config: {} },
      cards: {
        cards: [{
          id: "card-relax",
          title: "松弛操作",
          definition: "找到更短路径时更新距离。",
          related_frame_ids: ["f_002"],
        }],
      },
    })} />);

    fireEvent.click(screen.getByRole("button", { name: /知识卡片/ }));
    fireEvent.click(await screen.findByRole("button", { name: "f_002" }));

    await waitFor(() => expect(screen.getByRole("heading", { name: "教学视频" })).toBeInTheDocument());
    expect(screen.getByRole("status")).toHaveTextContent("已在教学视频中定位到 f_002");
    expect(screen.getByRole("button", { name: "选择镜头 2：执行松弛操作" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByRole("button", { name: /推演脚本/ })).not.toBeInTheDocument();
  });

  it("normalizes snake-case mindmap frame references and reports missing frames", async () => {
    render(<ModuleResultsPanel project={projectWith({
      frames,
      mindmap: {
        root: {
          id: "root",
          name: "最短路径",
          children: [{
            id: "relax",
            name: "松弛操作",
            related_frame_ids: ["f_404"],
          }],
        },
      },
    })} />);

    fireEvent.click(screen.getByRole("button", { name: /思维导图/ }));
    await waitFor(() => expect(screen.getByText("松弛操作")).toBeInTheDocument());
    fireEvent.click(screen.getByText("松弛操作"));
    fireEvent.click(await screen.findByRole("button", { name: "跳转推演 f_404" }));

    expect(screen.getByRole("status")).toHaveTextContent("未找到关联帧 f_404");
    expect(screen.getByRole("heading", { name: "思维导图" })).toBeInTheDocument();
  });

  it("assigns unique stable ids when generated mindmap nodes omit ids", async () => {
    render(<ModuleResultsPanel project={projectWith({
      mindmap: {
        root: {
          name: "冒泡排序",
          children: [
            { name: "比较相邻元素", children: [{ name: "交换逆序元素", children: [] }] },
            { name: "重复遍历", children: [] },
          ],
        },
      },
    })} />);

    expect(await screen.findByText("比较相邻元素")).toBeInTheDocument();
    expect(screen.getByText("交换逆序元素")).toBeInTheDocument();
    expect(screen.getByText("重复遍历")).toBeInTheDocument();
    expect(screen.getByText("4 个概念 · 拖动空白处平移 · 滚轮缩放")).toBeInTheDocument();
  });
});
