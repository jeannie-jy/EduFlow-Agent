/**
 * ModuleCard 组件测试。
 */

import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ModuleCard } from "./ModuleCard";
import type { ModuleInfo } from "@/services/generate";

// ============================================================================
// Helpers
// ============================================================================

function makeModuleInfo(overrides: Partial<ModuleInfo> = {}): ModuleInfo {
  return {
    module_id: "test_module",
    display_name: "测试模块",
    description: "这是一个测试模块的描述",
    icon: "test",
    category: "visual",
    priority: 3,
    estimated_seconds: 30,
    ...overrides,
  };
}

// ============================================================================
// Tests
// ============================================================================

describe("ModuleCard", () => {
  it("renders display name", () => {
    const info = makeModuleInfo({ display_name: "思维导图" });
    render(
      <ModuleCard info={info} selected={false} onToggle={vi.fn()} />
    );
    expect(screen.getByText("思维导图")).toBeInTheDocument();
  });

  it("renders description", () => {
    const info = makeModuleInfo({ description: "生成知识概念导图" });
    render(
      <ModuleCard info={info} selected={false} onToggle={vi.fn()} />
    );
    expect(screen.getByText("生成知识概念导图")).toBeInTheDocument();
  });

  it("renders category label in Chinese", () => {
    const info = makeModuleInfo({ category: "visual" });
    render(
      <ModuleCard info={info} selected={false} onToggle={vi.fn()} />
    );
    expect(screen.getByText("可视化")).toBeInTheDocument();
  });

  it("renders category label for export", () => {
    const info = makeModuleInfo({ category: "export" });
    render(
      <ModuleCard info={info} selected={false} onToggle={vi.fn()} />
    );
    expect(screen.getByText("导出")).toBeInTheDocument();
  });

  it("shows check icon when selected", () => {
    const info = makeModuleInfo();
    render(
      <ModuleCard info={info} selected={true} onToggle={vi.fn()} />
    );
    const button = screen.getByRole("button");
    // Check icon rendered by lucide-react inside the selection marker
    const svg = button.querySelector("svg.lucide-check");
    expect(svg).toBeTruthy();
  });

  it("does not show check icon when not selected", () => {
    const info = makeModuleInfo();
    render(
      <ModuleCard info={info} selected={false} onToggle={vi.fn()} />
    );
    const button = screen.getByRole("button");
    // No checkmark circle when unselected
    const checkIcons = button.querySelectorAll("svg.lucide-check");
    expect(checkIcons.length).toBe(0);
  });

  it("calls onToggle when clicked", async () => {
    const user = userEvent.setup();
    const onToggle = vi.fn();
    const info = makeModuleInfo();

    render(
      <ModuleCard info={info} selected={false} onToggle={onToggle} />
    );

    await user.click(screen.getByRole("button"));
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it("disables button when status is running", () => {
    const info = makeModuleInfo();
    render(
      <ModuleCard info={info} selected={false} onToggle={vi.fn()} status="running" />
    );
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("disables button when status is done", () => {
    const info = makeModuleInfo();
    render(
      <ModuleCard info={info} selected={false} onToggle={vi.fn()} status="done" />
    );
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("is not disabled when status is available", () => {
    const info = makeModuleInfo();
    render(
      <ModuleCard info={info} selected={false} onToggle={vi.fn()} status="available" />
    );
    expect(screen.getByRole("button")).not.toBeDisabled();
  });

  it("shows spinner when status is running", () => {
    const info = makeModuleInfo();
    render(
      <ModuleCard info={info} selected={false} onToggle={vi.fn()} status="running" />
    );
    // animate-spin class indicates running spinner
    const spinner = document.querySelector(".animate-spin");
    expect(spinner).toBeTruthy();
  });

  it("shows done checkmark when status is done", () => {
    const info = makeModuleInfo();
    render(
      <ModuleCard info={info} selected={false} onToggle={vi.fn()} status="done" />
    );
    // Check icon rendered for done state
    const doneSvg = document.querySelector("svg.lucide-check");
    expect(doneSvg).toBeTruthy();
  });

  it("shows error indicator when status is error", () => {
    const info = makeModuleInfo();
    render(
      <ModuleCard info={info} selected={false} onToggle={vi.fn()} status="error" />
    );
    // "!" character rendered for error
    expect(screen.getByText("!")).toBeInTheDocument();
  });

  it("applies selected border styles when selected", () => {
    const info = makeModuleInfo();
    render(
      <ModuleCard info={info} selected={true} onToggle={vi.fn()} />
    );
    const button = screen.getByRole("button");
    expect(button.className).toContain("border-[var(--interactive)]");
  });

  it("applies default border styles when not selected", () => {
    const info = makeModuleInfo();
    render(
      <ModuleCard info={info} selected={false} onToggle={vi.fn()} />
    );
    const button = screen.getByRole("button");
    expect(button.className).toContain("border-[var(--border)]");
  });

  it("applies opacity when disabled", () => {
    const info = makeModuleInfo();
    render(
      <ModuleCard info={info} selected={false} onToggle={vi.fn()} status="done" />
    );
    const button = screen.getByRole("button");
    expect(button.className).toContain("opacity-60");
  });
});
