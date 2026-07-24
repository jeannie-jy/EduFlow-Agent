import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { DijkstraDemo } from "./DijkstraDemo";

const renderPage = (ui: React.ReactElement) => render(ui);
const defaultMatchMedia = window.matchMedia;

function createReducedMotionMatchMedia(reduce: boolean) {
  return (query: string) =>
    ({
      matches: query === "(prefers-reduced-motion: reduce)" ? reduce : false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList;
}

afterEach(() => {
  window.matchMedia = defaultMatchMedia;
  Object.defineProperty(document, "visibilityState", {
    configurable: true,
    value: "visible",
  });
});

describe("DijkstraDemo", () => {
  it("does not autoplay when reduced motion is enabled", async () => {
    const user = userEvent.setup();
    window.matchMedia = createReducedMotionMatchMedia(true);
    renderPage(<DijkstraDemo />);

    await user.click(screen.getByRole("button", { name: "观看 60 秒演示" }));

    expect(screen.getByText("准备体验")).toBeVisible();
  });

  it("pauses when the document becomes hidden", async () => {
    const user = userEvent.setup();
    renderPage(<DijkstraDemo />);

    await user.click(screen.getByRole("button", { name: "观看 60 秒演示" }));
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      value: "hidden",
    });
    fireEvent(document, new Event("visibilitychange"));

    expect(screen.getByText("演示已暂停")).toBeVisible();
  });

  it("starts from a complete poster and only autoplays after activation", async () => {
    const user = userEvent.setup();
    renderPage(<DijkstraDemo compact />);

    expect(screen.getByText("设置源点")).toBeVisible();
    expect(screen.getByRole("button", { name: "观看 60 秒演示" })).toBeVisible();

    await user.click(screen.getByRole("button", { name: "观看 60 秒演示" }));

    expect(screen.getByRole("button", { name: "暂停演示" })).toBeVisible();
  });

  it("supports playback keyboard controls without stealing input keys", async () => {
    const user = userEvent.setup();
    renderPage(<DijkstraDemo />);

    await user.keyboard(" ");
    expect(screen.getByRole("button", { name: "暂停演示" })).toBeVisible();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("button", { name: "跳到第 2 帧" })).toHaveAttribute("aria-current", "step");
    await user.keyboard("{ArrowLeft}");
    expect(screen.getByRole("button", { name: "跳到第 1 帧" })).toHaveAttribute("aria-current", "step");

    const slider = screen.getByRole("slider", { name: "B 到 D 的边权重" });
    slider.focus();
    await user.keyboard("{ArrowRight}");

    expect(slider).toHaveFocus();
    expect(screen.getByRole("button", { name: "跳到第 1 帧" })).toHaveAttribute("aria-current", "step");
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

  it("keeps keyboard focus on the primary playback control as its state changes", async () => {
    const user = userEvent.setup();
    renderPage(<DijkstraDemo />);

    const primaryControl = screen.getByRole("button", { name: "观看 60 秒演示" });
    primaryControl.focus();
    await user.click(primaryControl);

    const pauseControl = screen.getByRole("button", { name: "暂停演示" });
    expect(pauseControl).toBe(primaryControl);
    expect(pauseControl).toHaveFocus();

    await user.click(pauseControl);
    const continueControl = screen.getByRole("button", { name: "继续演示" });
    expect(continueControl).toBe(primaryControl);
    expect(continueControl).toHaveFocus();
  });

  it("keeps the graph, timeline, and narration in compact mode while hiding parameters", () => {
    renderPage(<DijkstraDemo compact />);

    expect(screen.getByLabelText("Dijkstra 六节点交互图")).toBeVisible();
    expect(screen.getByRole("button", { name: "跳到第 6 帧" })).toBeVisible();
    expect(screen.getByText(/选择 A 作为源点/)).toBeVisible();
    expect(screen.queryByRole("slider", { name: "B 到 D 的边权重" })).not.toBeInTheDocument();
  });
});
