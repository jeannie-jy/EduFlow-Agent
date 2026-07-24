import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { DijkstraDemo } from "./DijkstraDemo";

const renderPage = (ui: React.ReactElement) => render(ui);

describe("DijkstraDemo", () => {
  it("starts from a complete poster and only autoplays after activation", async () => {
    const user = userEvent.setup();
    renderPage(<DijkstraDemo compact />);

    expect(screen.getByText("设置源点")).toBeVisible();
    expect(screen.getByRole("button", { name: "观看 60 秒演示" })).toBeVisible();

    await user.click(screen.getByRole("button", { name: "观看 60 秒演示" }));

    expect(screen.getByRole("button", { name: "暂停演示" })).toBeVisible();
  });

  it("changes B-D weight and exposes the recomputed distance", async () => {
    renderPage(<DijkstraDemo />);

    const input = screen.getByRole("slider", { name: "B 到 D 的边权重" });
    fireEvent.change(input, { target: { value: "3" } });

    expect(await screen.findByText("D 的最短距离变为 5")).toBeVisible();
    expect(screen.getByText("自由体验")).toBeVisible();
  });

  it("a timeline jump exits autoplay", async () => {
    const user = userEvent.setup();
    renderPage(<DijkstraDemo />);

    await user.click(screen.getByRole("button", { name: "观看 60 秒演示" }));
    await user.click(screen.getByRole("button", { name: "跳到第 6 帧" }));

    expect(screen.getByText("自由体验")).toBeVisible();
  });

  it("provides pause, skip, and replay controls", async () => {
    const user = userEvent.setup();
    renderPage(<DijkstraDemo />);

    await user.click(screen.getByRole("button", { name: "观看 60 秒演示" }));
    await user.click(screen.getByRole("button", { name: "暂停演示" }));
    expect(screen.getByText("演示已暂停")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "跳过演示" }));
    expect(screen.getByText("自由体验")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "重新播放演示" }));
    expect(screen.getByText("自动演示")).toBeVisible();
  });

  it("keeps the graph, timeline, and narration in compact mode while hiding parameters", () => {
    renderPage(<DijkstraDemo compact />);

    expect(screen.getByLabelText("Dijkstra 六节点交互图")).toBeVisible();
    expect(screen.getByRole("button", { name: "跳到第 6 帧" })).toBeVisible();
    expect(screen.getByText(/选择 A 作为源点/)).toBeVisible();
    expect(screen.queryByRole("slider", { name: "B 到 D 的边权重" })).not.toBeInTheDocument();
  });
});
