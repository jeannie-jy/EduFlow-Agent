import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ParameterExperiment } from "./ParameterExperiment";

const serviceMocks = vi.hoisted(() => ({
  previewRecomputeProject: vi.fn().mockResolvedValue({
    mode: "partial_frames",
    scope: { type: "from_frame", frame_ids: ["f2"] },
    changed_keys: ["speed"], dependencies: { speed: ["f2"] },
    direct_frame_ids: ["f2"], affected_frame_ids: ["f2", "f3"], protected_frame_ids: ["f1"],
    affected_module_ids: ["frames", "video"], module_dependencies: { frames: [], video: ["frames"] },
    fallback_used: false, reason: "重算直接依赖参数的最早帧及其状态后继", impact_token: "impact-1",
  }),
  recomputeProject: vi.fn().mockResolvedValue({ stream_url: "/api/projects/p1/generate/regenerate/stream" }),
  streamFromUrl: vi.fn((_url, options) => {
    options.onDone?.({ phase: "done", pct: 100 });
    return { close: vi.fn(), state: "closed" };
  }),
}));

vi.mock("@/services/parameters", () => ({
  previewRecomputeProject: serviceMocks.previewRecomputeProject,
  recomputeProject: serviceMocks.recomputeProject,
}));
vi.mock("@/services/generate", () => ({ streamFromUrl: serviceMocks.streamFromUrl }));

describe("ParameterExperiment", () => {
  it("submits only changed values and reports completion", async () => {
    serviceMocks.recomputeProject.mockClear();
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
    fireEvent.click(screen.getByRole("button", { name: "预览影响范围" }));
    await waitFor(() => expect(screen.getByRole("region", { name: "参数影响预览" })).toHaveTextContent("将重算 2 帧，保留 1 帧"));
    expect(screen.getByRole("region", { name: "参数影响预览" })).toHaveTextContent("下游产物将标记过期：video");
    expect(serviceMocks.recomputeProject).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "确认应用并重算" }));

    await waitFor(() => expect(serviceMocks.recomputeProject).toHaveBeenCalledWith("p1", { speed: 3 }, "impact-1"));
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

  it("applies local parameters without opening an agent stream", async () => {
    serviceMocks.streamFromUrl.mockClear();
    serviceMocks.recomputeProject.mockResolvedValueOnce({ mode: "local", stream_url: null });
    serviceMocks.previewRecomputeProject.mockResolvedValueOnce({
      mode: "local", scope: null, changed_keys: ["animation_speed"], dependencies: { animation_speed: [] },
      direct_frame_ids: [], affected_frame_ids: [], protected_frame_ids: ["f1"], fallback_used: false,
      affected_module_ids: [], module_dependencies: {},
      reason: "变更仅影响本地渲染属性，无需调用 Agent 重算帧", impact_token: "impact-local",
    });
    const onRecomputed = vi.fn();
    render(
      <ParameterExperiment
        projectId="p1"
        parameters={[{
          key: "animation_speed",
          label: "动画速度",
          param_type: "number",
          default_value: 1,
          current_value: 1,
          constraints: { min: 0.25, max: 3 },
          recompute_scope: "local",
        }]}
        onRecomputed={onRecomputed}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "展开参数（1）" }));
    fireEvent.change(screen.getByLabelText("动画速度"), { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: "预览影响范围" }));

    await waitFor(() => expect(screen.getByRole("region", { name: "参数影响预览" })).toHaveTextContent("仅更新本地渲染"));
    fireEvent.click(screen.getByRole("button", { name: "确认应用并重算" }));

    await waitFor(() => expect(onRecomputed).toHaveBeenCalled());
    expect(serviceMocks.streamFromUrl).not.toHaveBeenCalled();
    expect(screen.getByText("参数已应用，无需重新生成推演帧")).toBeInTheDocument();
  });
});
