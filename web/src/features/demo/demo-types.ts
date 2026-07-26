export type DemoMode = "poster" | "autoplay" | "paused" | "explore" | "completed";

export type DemoState = {
  mode: DemoMode;
  frameIndex: number;
  edgeWeight: number;
  speed: number;
};

export const initialDemoState: DemoState = {
  mode: "poster",
  frameIndex: 0,
  edgeWeight: 7,
  speed: 1,
};

export type DemoEvent =
  | { type: "PLAY" }
  | { type: "PAUSE" }
  | { type: "TICK"; totalFrames: number }
  | { type: "USER_FRAME"; frameIndex: number }
  | { type: "SET_EDGE_WEIGHT"; value: number }
  | { type: "SET_SPEED"; value: number }
  | { type: "REPLAY" }
  | { type: "SKIP" }
  | { type: "REDUCE_MOTION" };
