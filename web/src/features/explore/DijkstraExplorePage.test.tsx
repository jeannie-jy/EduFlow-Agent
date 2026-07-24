import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderPage } from "@/test/render";
import { DijkstraExplorePage } from "./DijkstraExplorePage";

describe("DijkstraExplorePage", () => {
  it("offers a complete public experience without authentication", () => {
    renderPage(<DijkstraExplorePage />);

    expect(screen.getByRole("heading", {
      name: "Dijkstra 最短路径交互推演",
    })).toBeVisible();
    expect(screen.getByRole("button", { name: "观看 60 秒演示" })).toBeVisible();
    expect(screen.getByRole("slider", { name: "B 到 D 的边权重" })).toBeVisible();
    expect(screen.getByRole("link", { name: "基于这个案例创建" }))
      .toHaveAttribute("href", "/app/new?template=dijkstra");
  });
});
