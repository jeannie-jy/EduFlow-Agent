import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { VideoStudioCard } from "./VideoStudioCard";

const exportMocks = vi.hoisted(() => ({
  cancelExportJob: vi.fn().mockResolvedValue({ job_id: "job-new", status: "cancelled" }),
  createExportJob: vi.fn().mockResolvedValue({ job_id: "job-new", status: "queued" }),
  getExportStatus: vi.fn().mockResolvedValue({
    job_id: "job-new",
    status: "completed",
    progress_pct: 100,
    artifacts: [],
    error_log: null,
  }),
}));

vi.mock("@/services/export", () => exportMocks);

describe("VideoStudioCard", () => {
  beforeEach(() => {
    window.localStorage.clear();
    exportMocks.createExportJob.mockClear();
    exportMocks.cancelExportJob.mockClear();
    exportMocks.getExportStatus.mockClear();
    exportMocks.getExportStatus.mockResolvedValue({
      job_id: "job-new",
      status: "completed",
      progress_pct: 100,
      artifacts: [],
      error_log: null,
    });
  });

  it("cancels an active durable render job", async () => {
    window.localStorage.setItem("eduflow:video-job:project-cancel", JSON.stringify({
      jobId: "job-active",
      status: "rendering",
      progress: 45,
      artifacts: [],
      error: null,
      config: {},
    }));
    exportMocks.getExportStatus.mockResolvedValue({
      job_id: "job-active",
      status: "rendering",
      progress_pct: 45,
      artifacts: [],
      error_log: null,
    });

    render(
      <VideoStudioCard
        projectId="project-cancel"
        videoValue={{ status: "ready", config: {} }}
        framesValue={{ artifact_version: "v1", frames: [] }}
      />,
    );

    fireEvent.click(await screen.findByRole("button", { name: "取消制作" }));
    await waitFor(() => expect(exportMocks.cancelExportJob).toHaveBeenCalledWith("job-active"));
    expect(await screen.findByText("制作已取消")).toBeInTheDocument();
  });

  it("creates a render job from editable output settings", async () => {
    render(
      <VideoStudioCard
        projectId="project-1"
        videoValue={{ status: "idle", config: {} }}
        framesValue={{ artifact_version: "v1", frames: [] }}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "视频画质 720p" }));
    fireEvent.click(screen.getByRole("button", { name: "视频帧率 24 fps" }));
    fireEvent.click(screen.getByRole("button", { name: "按当前设置开始制作" }));

    await waitFor(() => expect(exportMocks.createExportJob).toHaveBeenCalledWith("project-1", expect.objectContaining({
      quality: "m",
      fps: 24,
    })));
    await waitFor(() => expect(exportMocks.getExportStatus).toHaveBeenCalledWith("job-new"));
  });

  it("does not start automatically and resumes the same job after remount", async () => {
    exportMocks.getExportStatus.mockResolvedValue({
      job_id: "job-new",
      status: "rendering",
      progress_pct: 45,
      artifacts: [],
      error_log: null,
    });
    const props = {
      projectId: "project-resume",
      videoValue: { status: "ready", config: {} },
      framesValue: { artifact_version: "v1", frames: [] },
    };

    const first = render(<VideoStudioCard {...props} />);
    expect(exportMocks.createExportJob).not.toHaveBeenCalled();
    expect(screen.getByText("视频尚未开始制作。请先检查分镜并配置输出选项。")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "按当前设置开始制作" }));
    await waitFor(() => expect(exportMocks.getExportStatus).toHaveBeenCalledWith("job-new"));
    await waitFor(() => expect(window.localStorage.getItem("eduflow:video-job:project-resume")).toContain("job-new"));
    first.unmount();

    render(<VideoStudioCard {...props} />);
    await waitFor(() => expect(screen.getByText("正在制作")).toBeInTheDocument());
    expect(exportMocks.createExportJob).toHaveBeenCalledTimes(1);
    expect(exportMocks.getExportStatus).toHaveBeenCalledWith("job-new");
  });

  it("selects and previews storyboard shots with direct mouse controls", () => {
    render(
      <VideoStudioCard
        projectId="project-1"
        videoValue={{ status: "idle", config: {} }}
        framesValue={{
          artifact_version: "v1",
          frames: [
            { frame_id: "f1", title: "建立初始状态", narration: "观察初始数组", visual_objects: [] },
            { frame_id: "f2", title: "执行交换", narration: "交换两个元素", visual_objects: [] },
          ],
        }}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "选择镜头 2：执行交换" }));
    expect(screen.getByRole("button", { name: "选择镜头 2：执行交换" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getAllByText("交换两个元素")).not.toHaveLength(0);

    fireEvent.click(screen.getByRole("button", { name: "上一个镜头" }));
    expect(screen.getByRole("button", { name: "选择镜头 1：建立初始状态" })).toHaveAttribute("aria-pressed", "true");
  });

  it("gives every storyboard object its own scrollable content window", () => {
    const { container } = render(
      <VideoStudioCard
        projectId="project-scrollable-preview"
        videoValue={{ status: "idle", config: {} }}
        framesValue={{
          artifact_version: "v1",
          frames: [{
            frame_id: "f1",
            title: "滚动预览",
            narration: "完整查看内容",
            visual_objects: [{
              id: "long-array",
              type: "array",
              label: "长数组",
              cells: Array.from({ length: 20 }, (_, value) => ({ value })),
            }],
          }],
        }}
      />,
    );

    const content = container.querySelector(".video-storyboard-object__content");
    expect(content).toHaveClass("overflow-auto", "max-h-36");
    expect(content).toHaveAttribute("tabindex", "0");
    expect(container.querySelector(".video-storyboard-frame")).toHaveClass("aspect-video");
    expect(container.querySelector(".video-storyboard-preview")).not.toHaveClass("aspect-video");
    expect(container.querySelector(".video-storyboard-preview")).toHaveAttribute("data-layout", "adaptive-grid");
  });

  it("gives one long code block the right side and stacks supporting visuals on the left", () => {
    const { container } = render(
      <VideoStudioCard
        projectId="project-code-focus"
        videoValue={{ status: "idle", config: {} }}
        framesValue={{
          artifact_version: "v1",
          frames: [{
            frame_id: "f1",
            title: "代码讲解",
            narration: "左侧辅助信息，右侧完整代码",
            visual_objects: [
              { id: "array", type: "array", label: "输入", cells: [{ value: 3 }, { value: 1 }] },
              { id: "goal", type: "formula", label: "目标", latex: "a_0 \\le a_1" },
              { id: "code", type: "code_block", label: "伪代码", language: "text", code: "for each item:\n  compare(item)\n  update(item)" },
            ],
          }],
        }}
      />,
    );

    expect(container.querySelector(".video-storyboard-preview")).toHaveAttribute("data-layout", "code-focus");
    expect(container.querySelector('[data-visual-type="code_block"]')).toHaveClass("is-primary-code");
    expect(container.querySelectorAll(".is-supporting-object")).toHaveLength(2);
  });

  it("marks overloaded shots for splitting instead of relying on scrolling", () => {
    const { container } = render(
      <VideoStudioCard
        projectId="project-dense"
        videoValue={{ status: "idle", config: {} }}
        framesValue={{
          artifact_version: "v1",
          frames: [{
            frame_id: "f1",
            title: "复杂镜头",
            narration: "内容密度检查",
            visual_objects: Array.from({ length: 7 }, (_, index) => ({ id: `node-${index}`, type: "node", label: `节点 ${index}` })),
          }],
        }}
      />,
    );

    expect(container.querySelector(".video-storyboard-preview")).toHaveAttribute("data-frame-density", "dense");
    expect(screen.getByTitle("该镜头内容较多，建议拆分镜头以避免成片拥挤")).toBeInTheDocument();
  });

  it("opens a requested script frame inside the video storyboard", () => {
    render(
      <VideoStudioCard
        projectId="project-1"
        videoValue={{ status: "idle", config: {} }}
        targetFrameId="f2"
        framesValue={{
          artifact_version: "v1",
          frames: [
            { frame_id: "f1", title: "建立初始状态", narration: "观察初始数组", visual_objects: [] },
            { frame_id: "f2", title: "执行交换", narration: "交换两个元素", visual_objects: [] },
          ],
        }}
      />,
    );

    expect(screen.getByRole("button", { name: "选择镜头 2：执行交换" })).toHaveAttribute("aria-pressed", "true");
  });
});
