import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const simulationGraphProps = vi.hoisted(() => [] as Array<{ compact?: boolean }>);
let intersectionCallback: IntersectionObserverCallback | undefined;
let observerConstructionCount = 0;
let observerObserveCount = 0;
let observerDisconnectCount = 0;

class IntersectionObserverMock {
  constructor(callback: IntersectionObserverCallback) {
    observerConstructionCount += 1;
    intersectionCallback = callback;
  }

  observe() { observerObserveCount += 1; }
  unobserve() {}
  disconnect() { observerDisconnectCount += 1; }
  takeRecords() { return []; }
}

vi.mock("@/components/workbench/SimulationGraph", () => ({
  SimulationGraph: (props: { compact?: boolean }) => {
    simulationGraphProps.push({ compact: props.compact });
    return null;
  },
}));

import { DijkstraDemo } from "./DijkstraDemo";

describe("DijkstraDemo viewport behavior", () => {
  beforeEach(() => {
    simulationGraphProps.length = 0;
    observerConstructionCount = 0;
    observerObserveCount = 0;
    observerDisconnectCount = 0;
    globalThis.IntersectionObserver = IntersectionObserverMock as unknown as typeof IntersectionObserver;
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("defers to SimulationGraph viewport compactness in full mode and forces it in compact mode", () => {
    const { unmount } = render(<DijkstraDemo />);
    expect(simulationGraphProps.at(-1)).toEqual({ compact: undefined });

    unmount();
    render(<DijkstraDemo compact />);
    expect(simulationGraphProps.at(-1)).toEqual({ compact: true });
  });

  it("pauses autoplay when the demo leaves the viewport", () => {
    render(<DijkstraDemo />);
    const demo = screen.getByLabelText("Dijkstra 最短路径互动演示");

    fireEvent.click(screen.getByRole("button", { name: "观看交互演示" }));
    expect(screen.getByText("自动演示")).toBeVisible();

    const callback = intersectionCallback;
    expect(callback).toBeTypeOf("function");
    if (!callback) return;
    const bounds = demo.getBoundingClientRect();
    act(() => {
      callback(
        [{
          boundingClientRect: bounds,
          intersectionRatio: 0,
          intersectionRect: bounds,
          isIntersecting: false,
          rootBounds: null,
          target: demo,
          time: 0,
        }],
        {} as IntersectionObserver,
      );
    });

    expect(screen.getByText("演示已暂停")).toBeVisible();
  });

  it("keeps one observer across autoplay frame ticks and re-observes on mode transitions", () => {
    vi.useFakeTimers();
    const { unmount } = render(<DijkstraDemo />);
    const posterConstructionCount = observerConstructionCount;

    fireEvent.click(screen.getByRole("button", { name: "观看交互演示" }));
    const autoplayConstructionCount = observerConstructionCount;
    const autoplayObserveCount = observerObserveCount;
    const autoplayDisconnectCount = observerDisconnectCount;
    expect(autoplayConstructionCount).toBeGreaterThan(posterConstructionCount);

    act(() => vi.advanceTimersByTime(1400));
    expect(screen.getByRole("button", { name: "跳到第 2 帧" })).toHaveAttribute("aria-current", "step");
    expect(observerConstructionCount).toBe(autoplayConstructionCount);
    expect(observerObserveCount).toBe(autoplayObserveCount);
    expect(observerDisconnectCount).toBe(autoplayDisconnectCount);

    fireEvent.click(screen.getByRole("button", { name: "暂停演示" }));
    expect(observerConstructionCount).toBe(autoplayConstructionCount + 1);
    expect(observerObserveCount).toBe(autoplayObserveCount + 1);
    expect(observerDisconnectCount).toBe(autoplayDisconnectCount + 1);

    unmount();
    expect(observerDisconnectCount).toBe(autoplayDisconnectCount + 2);
  });
});
