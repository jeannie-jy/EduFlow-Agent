import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MindmapView, type MindmapNode } from "./MindmapView";

const root: MindmapNode = {
  id: "root",
  name: "Dijkstra 算法",
  type: "definition",
  children: [
    {
      id: "relax",
      name: "松弛操作",
      type: "core_mechanism",
      relatedFrameIds: ["f_003"],
      children: [{ id: "distance", name: "距离更新", type: "extension" }],
    },
  ],
};

describe("MindmapView", () => {
  it("supports node selection and related-frame navigation", async () => {
    const onNodeClick = vi.fn();
    const onFrameClick = vi.fn();
    render(<MindmapView root={root} onNodeClick={onNodeClick} onFrameClick={onFrameClick} />);

    await waitFor(() => expect(screen.getByText("松弛操作")).toBeInTheDocument());
    fireEvent.click(screen.getByText("松弛操作"));
    expect(onNodeClick).toHaveBeenCalledWith("relax");

    fireEvent.click(screen.getByRole("button", { name: "跳转推演 f_003" }));
    expect(onFrameClick).toHaveBeenCalledWith("f_003");
  });

  it("collapses branches and finds a concept from the search field", async () => {
    const onNodeClick = vi.fn();
    render(<MindmapView root={root} onNodeClick={onNodeClick} />);

    await waitFor(() => expect(screen.getByText("距离更新")).toBeInTheDocument());
    fireEvent.doubleClick(screen.getByText("松弛操作"));
    await waitFor(() => expect(screen.queryByText("距离更新")).not.toBeInTheDocument());

    fireEvent.doubleClick(screen.getByText("松弛操作"));
    const search = screen.getByLabelText("搜索思维导图概念");
    fireEvent.change(search, { target: { value: "距离" } });
    fireEvent.keyDown(search, { key: "Enter" });
    expect(onNodeClick).toHaveBeenCalledWith("distance");
  });
});
