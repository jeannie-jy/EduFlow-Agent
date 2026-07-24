import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const simulationGraphProps = vi.hoisted(() => [] as Array<{ compact?: boolean }>);
let intersectionCallback: IntersectionObserverCallback | undefined;

class IntersectionObserverMock {
  constructor(callback: IntersectionObserverCallback) {
    intersectionCallback = callback;
  }

  observe() {}
  unobserve() {}
  disconnect() {}
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
    globalThis.IntersectionObserver = IntersectionObserverMock as unknown as typeof IntersectionObserver;
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
});
