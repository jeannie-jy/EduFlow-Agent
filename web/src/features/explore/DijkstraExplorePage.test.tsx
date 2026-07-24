import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderPage } from "@/test/render";
import { DijkstraExplorePage } from "./DijkstraExplorePage";

describe("DijkstraExplorePage", () => {
  it("offers a complete public experience without authentication", async () => {
    renderPage(<DijkstraExplorePage />);

    expect(screen.getByRole("heading", {
      name: "Dijkstra 最短路径交互推演",
    })).toBeVisible();
    const primaryDemoControl = screen.getByRole("button", { name: "观看 60 秒演示" });
    expect(primaryDemoControl).toBeVisible();
    await waitFor(() => expect(primaryDemoControl).toHaveFocus());
    expect(screen.getByRole("slider", { name: "B 到 D 的边权重" })).toBeVisible();
    expect(screen.getByRole("link", { name: "基于这个案例创建" }))
      .toHaveAttribute("href", "/app/new?template=dijkstra");
  });
});
