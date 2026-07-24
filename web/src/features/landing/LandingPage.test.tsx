import { fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { renderPage } from "@/test/render";
import { LandingPage } from "./LandingPage";
import { processSteps, templates } from "./landing-content";

const landingStyles = readFileSync(resolve(process.cwd(), "src/styles/globals.css"), "utf8");

const expectedProcessSteps = [
  ["理解知识", "识别学习目标、先修知识和常见误区"],
  ["规划教学", "安排从直觉、实例到总结的教学顺序"],
  ["生成推演", "把知识变化组织成连续、可操作的帧"],
  ["检查质量", "检查知识正确性、状态连续性和教学清晰度"],
  ["输出成果", "生成交互页面、讲解文本、字幕和视频"],
] as const;

const expectedTemplates = [
  ["Dijkstra", "图算法", "14 帧", "约 6 分钟"],
  ["冒泡排序", "数据结构", "12 帧", "约 4 分钟"],
  ["Round Robin", "操作系统", "16 帧", "约 7 分钟"],
] as const;

class IntersectionObserverMock {
  private readonly callback: IntersectionObserverCallback;

  constructor(callback: IntersectionObserverCallback) {
    this.callback = callback;
  }

  observe(target: Element) {
    this.callback([{ isIntersecting: true, target } as IntersectionObserverEntry], this as unknown as IntersectionObserver);
  }

  unobserve() {}
  disconnect() {}
  takeRecords() { return []; }
}

globalThis.IntersectionObserver = IntersectionObserverMock as unknown as typeof IntersectionObserver;

describe("LandingPage", () => {
  beforeEach(() => {
    Object.defineProperty(window, "scrollY", { configurable: true, value: 0 });
  });

  it("explains the product and exposes the public, creation, and native root-qualified navigation paths", () => {
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
    expect(screen.getByRole("heading", { name: "我想理解一个知识点" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "我想创建教学推演" })).toBeVisible();
    expect(screen.queryByText("助教")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "教学内容值得被认真校对" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "不必从空白开始" })).toBeVisible();
    expect(screen.getByLabelText("Dijkstra 最短路径互动演示")).toBeVisible();
    expect(screen.getByRole("region", { name: "距离表（从 A 出发）" })).toBeVisible();
    expect(screen.getByText(/选择 A 作为源点/)).toBeVisible();
    expect(screen.getByRole("button", { name: "跳到第 6 帧" })).toBeVisible();
  });

  it("renders the complete process, two audience paths, and honest template previews in narrative order", () => {
    renderPage(<LandingPage />);

    expect(processSteps).toEqual(expectedProcessSteps);
    const processLedger = screen.getByRole("list", { name: "教学推演的五个步骤" });
    const processRows = within(processLedger).getAllByRole("listitem");
    expect(processRows).toHaveLength(5);
    expectedProcessSteps.forEach(([title, description], index) => {
      expect(processRows[index]).toHaveTextContent(`0${index + 1}${title}${description}`);
    });

    const audienceCards = document.querySelectorAll("#audiences .landing-audience-path");
    expect(audienceCards).toHaveLength(2);
    expect(audienceCards[0]).toHaveTextContent("学生：我想理解一个知识点");
    expect(audienceCards[1]).toHaveTextContent("教师：我想创建教学推演");
    expect(screen.getByRole("link", { name: "体验学生推演" })).toHaveAttribute("href", "/explore/dijkstra");
    expect(screen.getByRole("link", { name: "开始创建推演" })).toHaveAttribute("href", "/app/new");
    expect(screen.queryByText("助教")).not.toBeInTheDocument();
    expect(screen.queryByText("管理员")).not.toBeInTheDocument();

    const templateCards = document.querySelectorAll("#templates .landing-template");
    expect(templateCards).toHaveLength(3);
    expect(templates).toEqual(expectedTemplates);
    expectedTemplates.forEach(([name, category, frames, duration], index) => {
      for (const value of [name, category, frames, duration]) {
        expect(templateCards[index]).toHaveTextContent(value);
      }
    });
    expect(screen.getByText("推演对象：加权图")).toBeVisible();
    expect(screen.getByText("推演对象：数组交换")).toBeVisible();
    expect(screen.getByText("推演对象：进程队列")).toBeVisible();
    expect(screen.getByLabelText("Dijkstra 静态预览：节点 A 到 C 的距离从 ∞ 更新为 2")).toBeVisible();
    expect(screen.getByLabelText("冒泡排序静态预览：5 与 3 交换后为 [3, 5, 8]")).toBeVisible();
    expect(screen.getByLabelText("Round Robin 静态预览：进程 B 在 2 ms 时间片后回到队尾")).toBeVisible();

    expect(screen.getByRole("link", { name: "体验 Dijkstra 案例" })).toHaveAttribute("href", "/explore/dijkstra");
    expect(screen.queryByRole("link", { name: "体验 冒泡排序 案例" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "体验 Round Robin 案例" })).not.toBeInTheDocument();
    expect(screen.getAllByText("公开案例筹备中")).toHaveLength(2);
    expect(screen.getByRole("link", { name: "基于 Dijkstra 模板创建" })).toHaveAttribute("href", "/app/new?template=Dijkstra");
    expect(screen.getByRole("link", { name: "基于 冒泡排序 模板创建" })).toHaveAttribute("href", "/app/new?template=%E5%86%92%E6%B3%A1%E6%8E%92%E5%BA%8F");
    expect(screen.getByRole("link", { name: "基于 Round Robin 模板创建" })).toHaveAttribute("href", "/app/new?template=Round%20Robin");

    expect(Array.from(document.querySelectorAll("main > section")).map((section) => section.id || section.getAttribute("aria-labelledby"))).toEqual([
      "landing-hero-title",
      "product",
      "audiences",
      "capabilities-heading",
      "templates",
      "final-action-heading",
    ]);
  });

  it("leaves root-qualified section navigation to the browser instead of React Router", async () => {
    const user = userEvent.setup();
    renderPage(<LandingPage />);

    const desktopLink = screen.getByRole("link", { name: "产品原理" });
    const desktopClick = new MouseEvent("click", { bubbles: true, button: 0, cancelable: true });
    fireEvent(desktopLink, desktopClick);
    expect(desktopLink).not.toHaveAttribute("data-discover");
    expect(desktopClick.defaultPrevented).toBe(false);

    await user.click(screen.getByRole("button", { name: "打开导航" }));
    const mobileLink = within(screen.getByRole("navigation", { name: "移动主导航" }))
      .getByRole("link", { name: "交互案例" });
    const mobileClick = new MouseEvent("click", { bubbles: true, button: 0, cancelable: true });
    fireEvent(mobileLink, mobileClick);
    expect(mobileLink).not.toHaveAttribute("data-discover");
    expect(mobileClick.defaultPrevented).toBe(false);
    expect(screen.queryByRole("navigation", { name: "移动主导航" })).not.toBeInTheDocument();
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

  it("keeps the hero intrinsic while applying dense desktop demo rules and target offsets", () => {
    expect(landingStyles).not.toMatch(/\.landing-hero\s*\{[^}]*\b(?:min-)?height:/);
    expect(landingStyles).not.toContain("height: calc(100svh - 7rem)");
    expect(landingStyles).toContain("margin-inline: clamp(-1.5rem, -1.75vw, -0.25rem);");
    expect(landingStyles).toContain(".landing-hero__demo-plate .dijkstra-demo.dijkstra-demo--compact .dijkstra-demo__graph { min-height: 10.5rem; }");
    expect(landingStyles).toContain(".landing-hero__demo-plate .demo-status-table { padding: 0.35rem 0.55rem; }");
    expect(landingStyles).toContain(".landing-hero__demo-plate .demo-timeline__track { margin-top: 0.3rem; }");
    expect(landingStyles).toMatch(/#product,\s*#examples,\s*#audiences,\s*#templates \{\s*scroll-margin-top:/);
  });

  it("reserves first-viewport space for the next chapter without clipping the compact demo", () => {
    expect(landingStyles).toContain(".landing-hero__content { padding-top: 1rem; }");
    expect(landingStyles).toContain(".landing-hero__examples { margin: 0.6rem 0 0.35rem; }");
    expect(landingStyles).toContain(".landing-hero__demo-plate .dijkstra-demo { gap: 0.25rem; padding: 0.4rem 0.55rem; }");
    expect(landingStyles).toContain(".landing-hero__demo-plate .demo-status-table th,");
    expect(landingStyles).toContain(".landing-hero__demo-plate .demo-timeline__item p { font-size: 0.6rem; line-height: 1.1; }");
    expect(landingStyles).not.toMatch(/\.landing-hero\s*\{[^}]*\boverflow:\s*hidden/);
  });
});
