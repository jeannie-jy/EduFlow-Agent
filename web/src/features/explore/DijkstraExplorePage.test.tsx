import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { renderPage } from "@/test/render";
import { DijkstraExplorePage } from "./DijkstraExplorePage";

describe("DijkstraExplorePage", () => {
  it("offers a complete public experience without authentication", async () => {
    const user = userEvent.setup();
    renderPage(<DijkstraExplorePage />);

    expect(screen.getByRole("heading", {
      name: "Dijkstra 最短路径交互推演",
    })).toBeVisible();
    const loadingStatus = screen.getByText("正在加载交互演示…");
    expect(loadingStatus).toHaveAttribute("role", "status");
    const primaryDemoControl = await screen.findByRole("button", { name: "观看交互演示" });
    expect(primaryDemoControl).toBeVisible();
    expect(document.body).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("link", { name: "EduFlow 首页" })).toHaveFocus();
    expect(screen.getByRole("slider", { name: "B 到 D 的边权重" })).toBeVisible();
    expect(screen.getByRole("link", { name: "基于这个案例创建" }))
      .toHaveAttribute("href", "/app/new?template=dijkstra");
  });
});
