import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useDemoPlayback } from "./useDemoPlayback";

let reducedMotion = false;

vi.mock("motion/react", () => ({
  useReducedMotion: () => reducedMotion,
}));

afterEach(() => {
  cleanup();
  reducedMotion = false;
  vi.useRealTimers();
});

describe("useDemoPlayback", () => {
  it("starts as a poster and only advances after an explicit play action", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useDemoPlayback(3));

    expect(result.current.state).toMatchObject({ mode: "poster", frameIndex: 0 });
    act(() => vi.advanceTimersByTime(2800));
    expect(result.current.state.frameIndex).toBe(0);

    act(() => result.current.play());
    expect(result.current.state.mode).toBe("autoplay");
    act(() => vi.advanceTimersByTime(1400));
    expect(result.current.state.frameIndex).toBe(1);
  });

  it("hands autoplay to explore when a user jumps to a frame", () => {
    const { result } = renderHook(() => useDemoPlayback(8));

    act(() => result.current.play());
    act(() => result.current.goToFrame(5));

    expect(result.current.state).toMatchObject({ mode: "explore", frameIndex: 5 });
  });

  it("hands autoplay to explore when a user changes edge weight", () => {
    const { result } = renderHook(() => useDemoPlayback(8));

    act(() => result.current.play());
    act(() => result.current.setEdgeWeight(3));

    expect(result.current.state).toMatchObject({
      mode: "explore",
      edgeWeight: 3,
      frameIndex: 0,
    });
  });

  it("pauses autoplay when the document becomes hidden", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useDemoPlayback(3));

    act(() => result.current.play());
    Object.defineProperty(document, "visibilityState", { configurable: true, value: "hidden" });
    act(() => document.dispatchEvent(new Event("visibilitychange")));

    expect(result.current.state.mode).toBe("paused");
    act(() => vi.advanceTimersByTime(1400));
    expect(result.current.state.frameIndex).toBe(0);
  });

  it("returns to the poster when reduced motion becomes active", () => {
    const { result, rerender } = renderHook(() => useDemoPlayback(3));

    act(() => result.current.play());
    reducedMotion = true;
    rerender();

    expect(result.current.state.mode).toBe("poster");
  });

  it("keeps reduced-motion users on the poster when they play or replay", () => {
    vi.useFakeTimers();
    reducedMotion = true;
    const setTimeoutSpy = vi.spyOn(window, "setTimeout");
    const { result } = renderHook(() => useDemoPlayback(3));

    act(() => result.current.play());
    act(() => result.current.replay());
    act(() => vi.advanceTimersByTime(2800));

    expect(result.current.state).toMatchObject({ mode: "poster", frameIndex: 0 });
    expect(setTimeoutSpy).not.toHaveBeenCalled();
  });
});
