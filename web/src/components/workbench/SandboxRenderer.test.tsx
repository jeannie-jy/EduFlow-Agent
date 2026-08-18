import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SandboxRenderer } from "./SandboxRenderer";

describe("SandboxRenderer", () => {
  it("embeds the shared interactive-demo visual system without a network dependency", async () => {
    render(<SandboxRenderer code={'const InteractiveDemo = () => <div className="eduflow-demo">demo</div>;'} />);

    const frame = await screen.findByTitle("交互推演");
    expect(frame).toHaveAttribute("srcdoc", expect.stringContaining(".eduflow-demo__stage"));
    expect(frame).toHaveAttribute("srcdoc", expect.stringContaining(".eduflow-demo__timeline-item.is-current"));
    expect(frame).toHaveAttribute("srcdoc", expect.stringContaining(".eduflow-demo {"));
    expect(frame).toHaveAttribute("srcdoc", expect.not.stringContaining("cdn.tailwindcss.com"));
    expect(frame.className).toContain("min-h-[760px]");
  });

  it("locally compiles Tailwind classes used by legacy generated artifacts", async () => {
    render(<SandboxRenderer code={'const InteractiveDemo = () => <div className="grid grid-cols-2 gap-4 p-6 rounded-xl">legacy</div>;'} />);

    const frame = await screen.findByTitle("交互推演");
    expect(frame).toHaveAttribute("srcdoc", expect.stringContaining(".grid-cols-2"));
    expect(frame).toHaveAttribute("srcdoc", expect.stringContaining(".gap-4"));
    expect(frame).toHaveAttribute("srcdoc", expect.stringContaining(".p-6"));
    expect(frame).toHaveAttribute("srcdoc", expect.stringContaining(".rounded-xl"));
    expect(frame).toHaveAttribute("srcdoc", expect.stringContaining('data-sandbox-action="primary"'));
    expect(frame).toHaveAttribute("srcdoc", expect.stringContaining('data-sandbox-controls="true"'));
  });
});
