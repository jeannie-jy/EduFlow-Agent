import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { VideoStudioCard } from "./VideoStudioCard";

const exportMocks = vi.hoisted(() => ({
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
    fireEvent.click(screen.getByRole("button", { name: "开始渲染" }));

    await waitFor(() => expect(exportMocks.createExportJob).toHaveBeenCalledWith("project-1", expect.objectContaining({
      quality: "m",
      fps: 24,
    })));
    await waitFor(() => expect(exportMocks.getExportStatus).toHaveBeenCalledWith("job-new"));
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
});
