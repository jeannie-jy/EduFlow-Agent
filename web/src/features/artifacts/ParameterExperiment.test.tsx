import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ParameterExperiment } from "./ParameterExperiment";

const serviceMocks = vi.hoisted(() => ({
  recomputeProject: vi.fn().mockResolvedValue({ stream_url: "/api/projects/p1/generate/regenerate/stream" }),
  streamFromUrl: vi.fn((_url, options) => {
    options.onDone?.({ phase: "done", pct: 100 });
    return { close: vi.fn(), state: "closed" };
  }),
}));

vi.mock("@/services/parameters", () => ({ recomputeProject: serviceMocks.recomputeProject }));
vi.mock("@/services/generate", () => ({ streamFromUrl: serviceMocks.streamFromUrl }));

describe("ParameterExperiment", () => {
  it("submits only changed values and reports completion", async () => {
    const onRecomputed = vi.fn();
    render(
      <ParameterExperiment
        projectId="p1"
        parameters={[{
          key: "speed",
          label: "速度",
          param_type: "number",
          default_value: 1,
          current_value: 1,
          constraints: { min: 1, max: 5 },
          recompute_scope: "all_frames",
        }]}
        onRecomputed={onRecomputed}
      />,
    );

    expect(screen.queryByLabelText("速度")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "展开参数（1）" }));
    fireEvent.change(screen.getByLabelText("速度"), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "应用并重算" }));

    await waitFor(() => expect(serviceMocks.recomputeProject).toHaveBeenCalledWith("p1", { speed: 3 }));
    expect(screen.getByText("参数已应用，推演已更新")).toBeInTheDocument();
    expect(onRecomputed).toHaveBeenCalled();
  });

  it("keeps parameters collapsed by default and exposes a readable summary", () => {
    render(
      <ParameterExperiment
        projectId="p1"
        parameters={[{
          key: "speed",
          label: "速度",
          param_type: "number",
          default_value: 1,
          current_value: 1,
          constraints: { min: 1, max: 5 },
          recompute_scope: "all_frames",
        }]}
      />,
    );

    expect(screen.getByLabelText("当前参数摘要")).toHaveTextContent("速度：1");
    expect(screen.getByRole("button", { name: "展开参数（1）" })).toHaveAttribute("aria-expanded", "false");
  });
});
