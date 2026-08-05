/**
 * ModuleSelector 组件测试。
 */

import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ModuleSelector } from "./ModuleSelector";
import type { ModuleInfo } from "@/services/generate";

// ============================================================================
// Helpers
// ============================================================================

function makeModules(): ModuleInfo[] {
  return [
    {
      module_id: "mindmap",
      display_name: "思维导图",
      description: "生成知识概念导图",
      icon: "mindmap",
      category: "visual",
      priority: 1,
      estimated_seconds: 15,
    },
    {
      module_id: "cards",
      display_name: "知识卡片",
      description: "生成概念知识卡片",
      icon: "cards",
      category: "visual",
      priority: 2,
      estimated_seconds: 20,
    },
    {
      module_id: "quiz",
      display_name: "小练习",
      description: "自动生成练习题",
      icon: "quiz",
      category: "interactive",
      priority: 3,
      estimated_seconds: 25,
    },
    {
      module_id: "frames",
      display_name: "交互推演",
      description: "逐帧交互式演示",
      icon: "frames",
      category: "interactive",
      priority: 4,
      estimated_seconds: 40,
    },
    {
      module_id: "video",
      display_name: "教学视频",
      description: "导出 Manim 视频",
      icon: "video",
      category: "export",
      priority: 5,
      estimated_seconds: 120,
    },
  ];
}

// ============================================================================
// Tests
// ============================================================================

describe("ModuleSelector", () => {
  it("renders all module cards", () => {
    const modules = makeModules();
    render(<ModuleSelector modules={modules} onStart={vi.fn()} />);

    for (const mod of modules) {
      expect(screen.getByText(mod.display_name)).toBeInTheDocument();
    }
  });

  it("renders title and description text", () => {
    const modules = makeModules();
    render(<ModuleSelector modules={modules} onStart={vi.fn()} />);

    expect(screen.getByText("选择生成的产出形式")).toBeInTheDocument();
    expect(
      screen.getByText(/教学计划已生成/)
    ).toBeInTheDocument();
  });

  it("shows count of selected modules", () => {
    const modules = makeModules();
    render(<ModuleSelector modules={modules} onStart={vi.fn()} />);

    // Default: "frames" is pre-selected, so count should show 1
    expect(screen.getByText(/已选择 1 个模块/)).toBeInTheDocument();
  });

  it("toggles module selection on click", async () => {
    const user = userEvent.setup();
    const modules = makeModules();
    render(<ModuleSelector modules={modules} onStart={vi.fn()} />);

    // "思维导图" is not selected by default, "交互推演" is
    const mindmapCard = screen.getByText("思维导图").closest("button")!;
    expect(mindmapCard).not.toBeNull();

    // Click to select
    await user.click(mindmapCard);
    // After selecting mindmap + default frames, count should be 2
    expect(screen.getByText(/已选择 2 个模块/)).toBeInTheDocument();

    // Click again to deselect
    await user.click(mindmapCard);
    expect(screen.getByText(/已选择 1 个模块/)).toBeInTheDocument();
  });

  it("calls onStart with selected module IDs", async () => {
    const user = userEvent.setup();
    const onStart = vi.fn();
    const modules = makeModules();

    render(<ModuleSelector modules={modules} onStart={onStart} />);

    // Select mindmap too
    const mindmapCard = screen.getByText("思维导图").closest("button")!;
    await user.click(mindmapCard);

    // Click start button
    const startButton = screen.getByRole("button", { name: /开始生成/ });
    await user.click(startButton);

    expect(onStart).toHaveBeenCalledTimes(1);
    const selectedIds = onStart.mock.calls[0][0] as string[];
    expect(selectedIds).toContain("mindmap");
    expect(selectedIds).toContain("frames");  // default selected
  });

  it("disables start button when no modules selected", async () => {
    const modules = makeModules();

    render(
      <ModuleSelector modules={modules} onStart={vi.fn()} defaultSelected={[]} />
    );

    // Deselect the default "frames" - but wait, we set defaultSelected=[]
    const startButton = screen.getByRole("button", { name: /开始生成/ });
    expect(startButton).toBeDisabled();
  });

  it("disables start button when loading", () => {
    const modules = makeModules();
    render(<ModuleSelector modules={modules} onStart={vi.fn()} loading={true} />);

    const startButton = screen.getByRole("button", { name: /生成中/ });
    expect(startButton).toBeDisabled();
  });

  it("shows loading spinner when loading", () => {
    const modules = makeModules();
    render(<ModuleSelector modules={modules} onStart={vi.fn()} loading={true} />);

    const spinner = document.querySelector(".animate-spin");
    expect(spinner).toBeTruthy();
  });

  it("respects defaultSelected prop", () => {
    const modules = makeModules();
    render(
      <ModuleSelector
        modules={modules}
        onStart={vi.fn()}
        defaultSelected={["mindmap", "cards"]}
      />
    );

    expect(screen.getByText(/已选择 2 个模块/)).toBeInTheDocument();
  });

  it("renders modules in grid layout", () => {
    const modules = makeModules();
    render(<ModuleSelector modules={modules} onStart={vi.fn()} />);

    // The grid should contain cards organized by CSS grid
    const grid = document.querySelector(".grid");
    expect(grid).toBeTruthy();
    // Should have responsive grid classes
    expect(grid!.className).toContain("grid-cols-2");
    expect(grid!.className).toContain("sm:grid-cols-3");
    expect(grid!.className).toContain("lg:grid-cols-4");
  });

  it("can deselect default module", async () => {
    const user = userEvent.setup();
    const onStart = vi.fn();
    const modules = makeModules();

    render(<ModuleSelector modules={modules} onStart={onStart} />);

    // Default "frames" is selected, click to deselect
    const framesCard = screen.getByText("交互推演").closest("button")!;
    await user.click(framesCard);

    expect(screen.getByText(/已选择 0 个模块/)).toBeInTheDocument();
  });
});
