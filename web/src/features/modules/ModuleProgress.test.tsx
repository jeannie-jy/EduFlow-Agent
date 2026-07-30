/**
 * ModuleProgress 组件测试。
 */

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ModuleProgress } from "./ModuleProgress";
import type { ModuleProgressItem } from "./ModuleProgress";

// ============================================================================
// Helpers
// ============================================================================

function makeItem(overrides: Partial<ModuleProgressItem> = {}): ModuleProgressItem {
  return {
    module_id: "test_mod",
    display_name: "测试模块",
    status: "pending",
    ...overrides,
  };
}

function makeItems(
  statuses: Array<{ id: string; name: string; status: ModuleProgressItem["status"]; error?: string }>
): ModuleProgressItem[] {
  return statuses.map((s) => ({
    module_id: s.id,
    display_name: s.name,
    status: s.status,
    error: s.error,
  }));
}

// ============================================================================
// Tests
// ============================================================================

describe("ModuleProgress", () => {
  it("renders all module names", () => {
    const items = makeItems([
      { id: "mod_a", name: "思维导图", status: "done" },
      { id: "mod_b", name: "知识卡片", status: "running" },
    ]);

    render(<ModuleProgress modules={items} totalPct={50} />);
    expect(screen.getByText("思维导图")).toBeInTheDocument();
    expect(screen.getByText("知识卡片")).toBeInTheDocument();
  });

  it("shows progress percentage", () => {
    const items = makeItems([{ id: "mod_a", name: "A", status: "done" }]);
    render(<ModuleProgress modules={items} totalPct={75} />);
    expect(screen.getByText("75%")).toBeInTheDocument();
  });

  it("displays 'generating' message when modules are running", () => {
    const items = makeItems([
      { id: "mod_a", name: "A", status: "running" },
      { id: "mod_b", name: "B", status: "pending" },
    ]);
    render(<ModuleProgress modules={items} totalPct={30} />);
    expect(screen.getByText(/正在生成/)).toBeInTheDocument();
  });

  it("displays completion message when all done", () => {
    const items = makeItems([
      { id: "mod_a", name: "A", status: "done" },
      { id: "mod_b", name: "B", status: "done" },
    ]);
    render(<ModuleProgress modules={items} totalPct={100} />);
    expect(screen.getByText(/已完成 2\/2 个模块/)).toBeInTheDocument();
  });

  it("displays error count when some failed", () => {
    const items = makeItems([
      { id: "mod_a", name: "A", status: "done" },
      { id: "mod_b", name: "B", status: "error", error: "生成失败" },
    ]);
    render(<ModuleProgress modules={items} totalPct={90} />);
    expect(screen.getByText(/1 成功.*1 失败/)).toBeInTheDocument();
  });

  it("shows check icon for done modules", () => {
    const items = makeItems([{ id: "mod_a", name: "A", status: "done" }]);
    render(<ModuleProgress modules={items} totalPct={100} />);
    // CheckCircle2 renders a checkmark SVG
    const checkIcons = document.querySelectorAll(".text-green-500");
    expect(checkIcons.length).toBeGreaterThan(0);
  });

  it("shows spinner for running modules", () => {
    const items = makeItems([{ id: "mod_a", name: "A", status: "running" }]);
    render(<ModuleProgress modules={items} totalPct={50} />);
    const spinners = document.querySelectorAll(".animate-spin");
    expect(spinners.length).toBeGreaterThan(0);
  });

  it("shows clock icon for pending modules", () => {
    const items = makeItems([{ id: "mod_a", name: "A", status: "pending" }]);
    render(<ModuleProgress modules={items} totalPct={10} />);
    // Clock icon rendered with text-gray-400
    const clocks = document.querySelectorAll(".text-gray-400");
    expect(clocks.length).toBeGreaterThan(0);
  });

  it("shows error icon for failed modules", () => {
    const items = makeItems([
      { id: "mod_a", name: "A", status: "error", error: "oops" },
    ]);
    render(<ModuleProgress modules={items} totalPct={50} />);
    const errors = document.querySelectorAll(".text-red-500");
    // There should be XCircle (red) and the error text (red)
    expect(errors.length).toBeGreaterThan(0);
  });

  it("shows error message tooltip text", () => {
    const items = makeItems([
      { id: "mod_a", name: "A", status: "error", error: "LLM调用超时" },
    ]);
    render(<ModuleProgress modules={items} totalPct={50} />);
    // Error text uses title attribute for tooltip (CSS truncates display)
    const errorText = document.querySelector("[title='LLM调用超时']");
    expect(errorText).toBeTruthy();
  });

  it("renders progress bar with correct width", () => {
    const items = makeItems([{ id: "mod_a", name: "A", status: "done" }]);
    render(<ModuleProgress modules={items} totalPct={60} />);
    // Progress bar should have width: 60%
    const bar = document.querySelector(".bg-blue-500");
    expect(bar).toBeTruthy();
    expect((bar as HTMLElement).style.width).toBe("60%");
  });

  it("handles empty modules list", () => {
    render(<ModuleProgress modules={[]} totalPct={0} />);
    expect(screen.getByText("0%")).toBeInTheDocument();
  });

  it("handles single pending module", () => {
    const items = makeItems([{ id: "mod_a", name: "A", status: "pending" }]);
    render(<ModuleProgress modules={items} totalPct={10} />);
    expect(screen.getByText("A")).toBeInTheDocument();
    expect(screen.getByText("10%")).toBeInTheDocument();
  });
});
