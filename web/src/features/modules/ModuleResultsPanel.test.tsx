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
  it("jumps from a knowledge card to its related frame", async () => {
    render(<ModuleResultsPanel project={projectWith({
      frames,
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

    await waitFor(() => expect(screen.getByRole("heading", { name: "执行松弛操作" })).toBeInTheDocument());
    expect(screen.getByRole("status")).toHaveTextContent("已定位到 f_002");
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
});
