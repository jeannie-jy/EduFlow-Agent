import { initialDemoState, type DemoEvent, type DemoState } from "./demo-types";

export function demoReducer(state: DemoState, event: DemoEvent): DemoState {
  switch (event.type) {
    case "PLAY":
      return { ...state, mode: "autoplay" };
    case "PAUSE":
      return state.mode === "autoplay" ? { ...state, mode: "paused" } : state;
    case "TICK": {
      if (state.mode !== "autoplay") return state;
      const last = Math.max(0, event.totalFrames - 1);
      if (state.frameIndex >= last) return { ...state, mode: "completed" };
      return { ...state, frameIndex: Math.min(last, state.frameIndex + 1) };
    }
    case "USER_FRAME":
      return { ...state, mode: "explore", frameIndex: Math.max(0, event.frameIndex) };
    case "SET_EDGE_WEIGHT":
      return { ...state, mode: "explore", edgeWeight: event.value, frameIndex: 0 };
    case "SET_SPEED":
      return { ...state, speed: event.value };
    case "REPLAY":
      return { ...initialDemoState, mode: "autoplay" };
    case "SKIP":
      return { ...state, mode: "explore" };
    case "REDUCE_MOTION":
      return { ...state, mode: "poster" };
  }
}
