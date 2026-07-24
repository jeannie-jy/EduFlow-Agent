import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderPage } from "@/test/render";
import { LandingPage } from "./LandingPage";

describe("LandingPage", () => {
  it("explains the product and exposes public and creation paths", () => {
    renderPage(<LandingPage />);

    expect(screen.getByRole("heading", {
      name: "让抽象知识，变成可以亲手操控的推演",
    })).toBeVisible();
    expect(screen.getByRole("link", { name: "体验交互推演" }))
      .toHaveAttribute("href", "/explore/dijkstra");
    expect(screen.getByRole("link", { name: "创建新的推演" }))
      .toHaveAttribute("href", "/app/new");
    expect(screen.getByRole("navigation", { name: "主导航" })).toBeVisible();
    expect(screen.getByLabelText(/主题/)).toBeVisible();
  });
});
