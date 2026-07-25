import { describe, expect, it } from "vitest";
import { demoReducer } from "./demo-reducer";
import { initialDemoState } from "./demo-types";

describe("demoReducer", () => {
  it("starts only after PLAY", () => {
    expect(demoReducer(initialDemoState, { type: "PLAY" })).toMatchObject({
      mode: "autoplay",
      frameIndex: 0,
    });
  });

  it("pauses autoplay without changing an already paused state", () => {
    const playing = { ...initialDemoState, mode: "autoplay" as const };
    const paused = demoReducer(playing, { type: "PAUSE" });

    expect(paused.mode).toBe("paused");
    expect(demoReducer(paused, { type: "PAUSE" })).toBe(paused);
  });

  it("advances one frame until it completes at the final frame", () => {
    const playing = { ...initialDemoState, mode: "autoplay" as const, frameIndex: 1 };

    expect(demoReducer(playing, { type: "TICK", totalFrames: 3 })).toMatchObject({
      mode: "autoplay",
      frameIndex: 2,
    });
    expect(demoReducer({ ...playing, frameIndex: 2 }, { type: "TICK", totalFrames: 3 })).toMatchObject({
      mode: "completed",
      frameIndex: 2,
    });
  });

  it.each([
    ["poster", initialDemoState],
    ["paused", { ...initialDemoState, mode: "paused" as const, frameIndex: 1 }],
    ["explore after skip", { ...initialDemoState, mode: "explore" as const, frameIndex: 1 }],
    ["explore after a frame jump", { ...initialDemoState, mode: "explore" as const, frameIndex: 5 }],
    ["explore after an edge change", { ...initialDemoState, mode: "explore" as const, edgeWeight: 3 }],
    ["poster after reduced motion", { ...initialDemoState, mode: "poster" as const, frameIndex: 1 }],
  ])("ignores a stale tick while %s owns the demo", (_interruption, state) => {
    expect(demoReducer(state, { type: "TICK", totalFrames: 8 })).toBe(state);
  });

  it("hands control to explore after a user frame jump", () => {
    const playing = { ...initialDemoState, mode: "autoplay" as const };
    expect(demoReducer(playing, { type: "USER_FRAME", frameIndex: 5 })).toMatchObject({
      mode: "explore",
      frameIndex: 5,
    });
  });

  it("clamps a user frame jump at zero", () => {
    expect(demoReducer(initialDemoState, { type: "USER_FRAME", frameIndex: -2 })).toMatchObject({
      mode: "explore",
      frameIndex: 0,
    });
  });

  it("hands control to explore and resets the frame after a parameter change", () => {
    const playing = { ...initialDemoState, mode: "autoplay" as const, frameIndex: 4 };

    expect(demoReducer(playing, { type: "SET_EDGE_WEIGHT", value: 3 })).toMatchObject({
      mode: "explore",
      edgeWeight: 3,
      frameIndex: 0,
    });
  });

  it("updates speed without interrupting the current playback mode", () => {
    const playing = { ...initialDemoState, mode: "autoplay" as const };

    expect(demoReducer(playing, { type: "SET_SPEED", value: 1.5 })).toMatchObject({
      mode: "autoplay",
      speed: 1.5,
    });
  });

  it("resets all transient state before replay", () => {
    const changed = {
      mode: "explore" as const,
      frameIndex: 7,
      edgeWeight: 3,
      speed: 1.5,
    };
    expect(demoReducer(changed, { type: "REPLAY" })).toEqual({
      ...initialDemoState,
      mode: "autoplay",
    });
  });

  it("hands control to explore when the demo is skipped", () => {
    const playing = { ...initialDemoState, mode: "autoplay" as const };

    expect(demoReducer(playing, { type: "SKIP" }).mode).toBe("explore");
  });

  it("uses poster mode when reduced motion is requested", () => {
    const playing = { ...initialDemoState, mode: "autoplay" as const };
    expect(demoReducer(playing, { type: "REDUCE_MOTION" }).mode).toBe("poster");
  });
});
