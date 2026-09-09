import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  compileTailwindCss,
  SandboxRenderer,
  type SandboxRuntimeCompiler,
} from "./SandboxRenderer";

describe("SandboxRenderer", () => {
  const compiler = (utilityCss: string): SandboxRuntimeCompiler => vi.fn().mockResolvedValue({
    compiledJs: "const InteractiveDemo = () => React.createElement('div', null, 'demo');",
    utilityCss,
  });

  it("embeds the shared interactive-demo visual system without a network dependency", async () => {
    render(
      <SandboxRenderer
        code={'const InteractiveDemo = () => <div className="eduflow-demo">demo</div>;'}
        compileRuntime={compiler(".eduflow-demo-test { display: grid; }")}
      />,
    );

    const frame = await screen.findByTitle("交互推演");
    expect(frame).toHaveAttribute("srcdoc", expect.stringContaining(".eduflow-demo__stage"));
    expect(frame).toHaveAttribute("srcdoc", expect.stringContaining(".eduflow-demo__timeline-item.is-current"));
    expect(frame).toHaveAttribute("srcdoc", expect.stringContaining(".eduflow-demo {"));
    expect(frame).toHaveAttribute("srcdoc", expect.not.stringContaining("cdn.tailwindcss.com"));
    expect(frame.className).toContain("min-h-[760px]");
  });

  it("embeds locally compiled Tailwind classes used by legacy generated artifacts", async () => {
    const utilityCss = ".grid-cols-2{} .gap-4{} .p-6{} .rounded-xl{}";
    render(
      <SandboxRenderer
        code={'const InteractiveDemo = () => <div className="grid grid-cols-2 gap-4 p-6 rounded-xl">legacy</div>;'}
        compileRuntime={compiler(utilityCss)}
      />,
    );

    const frame = await screen.findByTitle("交互推演");
    expect(frame).toHaveAttribute("srcdoc", expect.stringContaining(".grid-cols-2"));
    expect(frame).toHaveAttribute("srcdoc", expect.stringContaining(".gap-4"));
    expect(frame).toHaveAttribute("srcdoc", expect.stringContaining(".p-6"));
    expect(frame).toHaveAttribute("srcdoc", expect.stringContaining(".rounded-xl"));
    expect(frame).toHaveAttribute("srcdoc", expect.stringContaining('data-sandbox-action="primary"'));
    expect(frame).toHaveAttribute("srcdoc", expect.stringContaining('data-sandbox-controls="true"'));
  });

  it("shows a stable user-facing error when runtime compilation fails", async () => {
    const failingCompiler: SandboxRuntimeCompiler = vi.fn().mockRejectedValue(new Error("compile failed"));
    render(<SandboxRenderer code="const InteractiveDemo = () => null;" compileRuntime={failingCompiler} />);

    expect(await screen.findByText("互动内容暂时无法展示")).toBeInTheDocument();
    expect(screen.queryByText("compile failed")).not.toBeInTheDocument();
  });

  it("compiles legacy Tailwind candidates with the production compiler", async () => {
    const css = await compileTailwindCss(
      'const InteractiveDemo = () => <div className="grid grid-cols-2 gap-4 p-6 rounded-xl">legacy</div>;',
    );

    expect(css).toContain(".grid-cols-2");
    expect(css).toContain(".gap-4");
    expect(css).toContain(".p-6");
    expect(css).toContain(".rounded-xl");
  });
});
