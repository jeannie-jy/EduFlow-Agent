import { fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { renderPage } from "@/test/render";
import { LandingPage } from "./LandingPage";

const landingStyles = readFileSync(resolve(process.cwd(), "src/styles/globals.css"), "utf8");

describe("LandingPage", () => {
  beforeEach(() => {
    Object.defineProperty(window, "scrollY", { configurable: true, value: 0 });
  });

  it("explains the product and exposes the public, creation, and root-qualified navigation paths", () => {
    renderPage(<LandingPage />);

    expect(screen.getByRole("heading", {
      name: "让抽象知识，变成可以亲手操控的推演",
    })).toBeVisible();
    expect(screen.getByRole("link", { name: "体验交互推演" }))
      .toHaveAttribute("href", "/explore/dijkstra");
    expect(screen.getByRole("link", { name: "创建新的推演" }))
      .toHaveAttribute("href", "/app/new");
    expect(screen.getByText("从一个知识点出发，自动生成教学计划、逐帧动画、交互参数和可导出的教学内容。"))
      .toBeVisible();
    expect(screen.getByRole("navigation", { name: "主导航" })).toBeVisible();
    expect(screen.getByLabelText(/主题/)).toBeVisible();

    expect(screen.getByRole("link", { name: "产品原理" })).toHaveAttribute("href", "/#product");
    expect(screen.getByRole("link", { name: "交互案例" })).toHaveAttribute("href", "/#examples");
    expect(screen.getByRole("link", { name: "使用场景" })).toHaveAttribute("href", "/#audiences");
    expect(screen.getByRole("link", { name: "模板库" })).toHaveAttribute("href", "/#templates");

    for (const target of ["product", "examples", "audiences", "templates"]) {
      expect(document.getElementById(target)?.tagName).toBe("SECTION");
    }
    expect(screen.getByRole("heading", { name: "从一个问题，到一场完整推演" })).toBeVisible();
    expect(screen.getByLabelText("Dijkstra 最短路径互动演示")).toBeVisible();
  });

  it("adds a paper surface after the header scroll threshold", () => {
    renderPage(<LandingPage />);
    Object.defineProperty(window, "scrollY", { configurable: true, value: 25 });
    fireEvent.scroll(window);

    expect(screen.getByLabelText("EduFlow 首页").closest("header")).toHaveClass("site-header--scrolled");
  });

  it("opens a keyboard-accessible mobile navigation and returns focus on escape", async () => {
    const user = userEvent.setup();
    renderPage(<LandingPage />);

    const trigger = screen.getByRole("button", { name: "打开导航" });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(trigger).toHaveAttribute("aria-controls", "site-mobile-navigation");

    await user.click(trigger);
    const mobileNavigation = screen.getByRole("navigation", { name: "移动主导航" });
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(within(mobileNavigation).getByRole("link", { name: "产品原理" }))
      .toHaveAttribute("href", "/#product");
    expect(within(mobileNavigation).getByRole("link", { name: "登录" })).toHaveAttribute("href", "/login");
    expect(within(mobileNavigation).getByRole("link", { name: "产品原理" })).toHaveFocus();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("navigation", { name: "移动主导航" })).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("closes the mobile navigation after selecting a section", async () => {
    const user = userEvent.setup();
    renderPage(<LandingPage />);

    await user.click(screen.getByRole("button", { name: "打开导航" }));
    await user.click(within(screen.getByRole("navigation", { name: "移动主导航" }))
      .getByRole("link", { name: "交互案例" }));

    expect(screen.queryByRole("navigation", { name: "移动主导航" })).not.toBeInTheDocument();
  });

  it("keeps the desktop hero within a viewport budget and offsets every section target", () => {
    expect(landingStyles).toMatch(/@media \(min-width: 901px\) and \(min-height: 820px\) \{\s*\.landing-hero \{[^}]*height: calc\(100svh - 7rem\);/);
    expect(landingStyles).toContain("margin-inline: clamp(-1.5rem, -1.75vw, -0.25rem);");
    expect(landingStyles).toMatch(/#product,\s*#examples,\s*#audiences,\s*#templates \{\s*scroll-margin-top:/);
  });
});
