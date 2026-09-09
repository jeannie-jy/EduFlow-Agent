import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { VersionHistoryPanel } from "./VersionHistoryPanel";

const serviceMocks = vi.hoisted(() => ({
  listVersions: vi.fn().mockResolvedValue({
    versions: [
      { id: "v2", version: 2, change_summary: "当前版本", created_at: "2026-09-06", is_current: true },
      { id: "v1", version: 1, change_summary: "初始版本", created_at: "2026-09-05", is_current: false },
    ],
  }),
  diffVersion: vi.fn().mockResolvedValue({
    from: { type: "version", id: "v1", version: 1 },
    to: { type: "current", id: "p1" },
    summary: {
      frames_added: 1, frames_removed: 0, frames_modified: 2,
      parameters_changed: 1, metadata_fields_changed: 0, frame_order_changed: false,
    },
    frames: { added: ["f3"], removed: [], modified: [], order_changed: false },
    parameters: [{ key: "size", change: "modified" }],
    metadata_changed: [],
  }),
  restoreVersion: vi.fn().mockResolvedValue({ restored_to_version: 1, id: "v1" }),
}));

vi.mock("@/services/versions", () => serviceMocks);

describe("VersionHistoryPanel", () => {
  it("previews a semantic diff before requiring restore confirmation", async () => {
    const onRestored = vi.fn();
    render(<VersionHistoryPanel projectId="p1" onRestored={onRestored} />);

    fireEvent.click(screen.getByRole("button", { name: "版本历史" }));
    await waitFor(() => expect(screen.getByText("当前", { selector: "span" })).toBeInTheDocument());
    await waitFor(() => expect(screen.getByRole("button", { name: /版本 1/ })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /版本 1/ }));

    await waitFor(() => expect(screen.getByRole("region", { name: "版本差异预览" })).toHaveTextContent("帧 +1 / -0 / 改 2"));
    expect(serviceMocks.restoreVersion).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "恢复此版本" }));
    expect(serviceMocks.restoreVersion).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "确认恢复版本 1" }));

    await waitFor(() => expect(serviceMocks.restoreVersion).toHaveBeenCalledWith("p1", "v1"));
    expect(onRestored).toHaveBeenCalled();
    expect(screen.getByRole("status")).toHaveTextContent("恢复前状态已自动存档");
  });
});
