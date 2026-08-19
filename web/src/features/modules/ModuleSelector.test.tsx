import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ModuleSelector } from "./ModuleSelector";
import type { ModuleInfo } from "@/services/generate";

const modules: ModuleInfo[] = [
  { module_id: "mindmap", display_name: "思维导图", description: "知识结构", icon: "mindmap", category: "visual", priority: 1, estimated_seconds: 15 },
  { module_id: "frames", display_name: "推演脚本", description: "视频内部数据", icon: "frames", category: "interactive", priority: 2, estimated_seconds: 40 },
  { module_id: "interactive_demo", display_name: "交互推演", description: "知识互动体验", icon: "play", category: "interactive", priority: 3, estimated_seconds: 40 },
  { module_id: "video", display_name: "教学视频", description: "视频成果", icon: "video", category: "export", priority: 4, estimated_seconds: 120 },
];

describe("ModuleSelector", () => {
  it("shows user-facing results but hides the internal storyboard", () => {
    render(<ModuleSelector modules={modules} onStart={vi.fn()} />);
    expect(screen.getByText("思维导图")).toBeInTheDocument();
    expect(screen.getByText("交互推演")).toBeInTheDocument();
    expect(screen.getByText("教学视频")).toBeInTheDocument();
    expect(screen.queryByText("推演脚本")).not.toBeInTheDocument();
  });

  it("starts empty and requires a visible result", () => {
    render(<ModuleSelector modules={modules} onStart={vi.fn()} defaultSelected={["frames"]} />);
    expect(screen.getByText(/已选择 0 个成果/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /开始生成/ })).toBeDisabled();
  });

  it("selects and deselects any user-facing result", async () => {
    const user = userEvent.setup();
    render(<ModuleSelector modules={modules} onStart={vi.fn()} />);
    await user.click(screen.getByText("交互推演").closest("button")!);
    expect(screen.getByText(/已选择 1 个成果/)).toBeInTheDocument();
    await user.click(screen.getByText("交互推演").closest("button")!);
    expect(screen.getByText(/已选择 0 个成果/)).toBeInTheDocument();
  });

  it("submits only visible selected module ids", async () => {
    const user = userEvent.setup();
    const onStart = vi.fn();
    render(<ModuleSelector modules={modules} onStart={onStart} defaultSelected={["frames", "interactive_demo"]} />);
    await user.click(screen.getByRole("button", { name: /开始生成/ }));
    expect(onStart).toHaveBeenCalledWith(["interactive_demo"]);
  });

  it("respects loading and optional button modes", () => {
    const { rerender } = render(<ModuleSelector modules={modules} onStart={vi.fn()} loading defaultSelected={["video"]} />);
    expect(screen.getByRole("button", { name: /生成中/ })).toBeDisabled();
    expect(document.querySelector(".animate-spin")).toBeTruthy();
    rerender(<ModuleSelector modules={modules} onStart={vi.fn()} showStartButton={false} />);
    expect(screen.queryByRole("button", { name: /开始生成/ })).not.toBeInTheDocument();
  });
});
