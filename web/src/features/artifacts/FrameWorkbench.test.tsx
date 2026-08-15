import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { FrameWorkbench } from "./FrameWorkbench";

const frameApi = vi.hoisted(() => ({
  updateFrame: vi.fn().mockResolvedValue({ id: "frame-db-id", updated_at: "2026-01-01" }),
  lockFrame: vi.fn().mockResolvedValue({ id: "frame-db-id", is_locked: true }),
}));

vi.mock("@/services/frames", () => frameApi);

const artifact = {
  schema_version: "1.0",
  artifact_version: "demo-v1",
  frames: [
    {
      frame_id: "f_001",
      title: "建立数组",
      learning_goal: "理解初始状态",
      narration: "先观察数组中的三个元素。",
      visual_objects: [
        {
          id: "array-main",
          type: "array",
          label: "待排序数组",
          cells: [{ value: 3 }, { value: 1 }, { value: 2 }],
        },
      ],
      state_snapshot: { active: 0 },
      checks: [],
    },
    {
      frame_id: "f_002",
      title: "交换元素",
      narration: "交换前两个元素。",
      visual_objects: [
        {
          id: "array-main",
          type: "array",
          label: "待排序数组",
          cells: [{ value: 1 }, { value: 3 }, { value: 2 }],
        },
      ],
      state_snapshot: { active: 1 },
      checks: [{ type: "order", message: "前两个元素有序" }],
    },
  ],
};

describe("FrameWorkbench", () => {
  it("renders visual objects and supports frame inspection", () => {
    render(<FrameWorkbench value={artifact} />);

    expect(screen.getByText("建立数组")).toBeInTheDocument();
    expect(screen.getByLabelText("待排序数组")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /下一帧/ }));
    expect(screen.getByText("交换元素")).toBeInTheDocument();
    expect(screen.getByText("active：1")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "检查" }));
    expect(screen.getByText("前两个元素有序")).toBeInTheDocument();
  });

  it("makes review scope explicit", () => {
    render(<FrameWorkbench value={artifact} />);
    fireEvent.click(screen.getByRole("button", { name: "确认当前帧" }));
    expect(screen.getByText("本次已确认")).toBeInTheDocument();
    expect(screen.getByText(/不会写回项目数据/)).toBeInTheDocument();
  });

  it("keeps browsing safe and exposes direct object and timeline navigation", () => {
    render(<FrameWorkbench value={artifact} projectId="project-1" />);

    expect(screen.getByRole("button", { name: "浏览" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: "编辑模式" }));
    expect(screen.getByRole("button", { name: "编辑模式" })).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(screen.getByRole("button", { name: "选择对象：待排序数组" }));
    expect(screen.getByRole("button", { name: "对象" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("array-main")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "跳转到第 2 帧：交换元素" }));
    expect(screen.getByText("交换元素")).toBeInTheDocument();
  });

  it("opens directly on a frame requested by another module", () => {
    render(<FrameWorkbench value={artifact} targetFrameId="f_002" />);

    expect(screen.getByText("交换元素")).toBeInTheDocument();
    expect(screen.getByText("2 / 2")).toBeInTheDocument();
  });

  it("edits, saves, and locks a frame through the existing APIs", async () => {
    render(<FrameWorkbench value={artifact} projectId="project-1" />);
    fireEvent.click(screen.getByRole("button", { name: "编辑" }));
    fireEvent.change(screen.getByLabelText("帧标题"), { target: { value: "新的标题" } });
    fireEvent.change(screen.getByLabelText("帧旁白"), { target: { value: "新的旁白" } });
    fireEvent.click(screen.getByRole("button", { name: "保存帧" }));

    await waitFor(() => expect(frameApi.updateFrame).toHaveBeenCalledWith("project-1", "f_001", {
      title: "新的标题",
      narration: "新的旁白",
    }));
    expect(screen.getByText("新的标题")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "锁定并保留当前帧" }));
    await waitFor(() => expect(frameApi.lockFrame).toHaveBeenCalledWith("project-1", "f_001", true));
    expect(screen.getByText("已锁定")).toBeInTheDocument();
  });
});
