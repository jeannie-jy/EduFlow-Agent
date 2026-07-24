import { useEffect, useReducer, useState } from "react";
import { useReducedMotion } from "motion/react";
import { demoReducer } from "./demo-reducer";
import { initialDemoState, type DemoState } from "./demo-types";

export type DemoPlaybackController = {
  state: DemoState;
  play(): void;
  pause(): void;
  replay(): void;
  skip(): void;
  goToFrame(frameIndex: number): void;
  setEdgeWeight(value: number): void;
  setSpeed(value: number): void;
};

function getReducedMotionMediaQuery() {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return null;
  return window.matchMedia("(prefers-reduced-motion: reduce)");
}

type NativeReducedMotionPreference = {
  available: boolean;
  matches: boolean;
};

function readNativeReducedMotionPreference(): NativeReducedMotionPreference {
  const mediaQuery = getReducedMotionMediaQuery();
  return { available: mediaQuery !== null, matches: mediaQuery?.matches ?? false };
}

export function useDemoPlayback(totalFrames: number): DemoPlaybackController {
  const [state, dispatch] = useReducer(demoReducer, initialDemoState);
  const reduceMotion = useReducedMotion();
  const [nativeReducedMotion, setNativeReducedMotion] = useState(readNativeReducedMotionPreference);
  const prefersReducedMotion = nativeReducedMotion.available
    ? nativeReducedMotion.matches
    : Boolean(reduceMotion);

  useEffect(() => {
    const mediaQuery = getReducedMotionMediaQuery();
    if (!mediaQuery) return;

    const handleChange = (event: MediaQueryListEvent) => {
      setNativeReducedMotion({ available: true, matches: event.matches });
      if (event.matches) dispatch({ type: "REDUCE_MOTION" });
    };

    setNativeReducedMotion({ available: true, matches: mediaQuery.matches });
    if (mediaQuery.matches) dispatch({ type: "REDUCE_MOTION" });
    mediaQuery.addEventListener("change", handleChange);
    return () => mediaQuery.removeEventListener("change", handleChange);
  }, []);

  useEffect(() => {
    if (prefersReducedMotion) dispatch({ type: "REDUCE_MOTION" });
  }, [prefersReducedMotion]);

  useEffect(() => {
    if (prefersReducedMotion || state.mode !== "autoplay") return;

    const timer = window.setTimeout(
      () => dispatch({ type: "TICK", totalFrames }),
      1400 / state.speed,
    );
    return () => window.clearTimeout(timer);
  }, [prefersReducedMotion, state.mode, state.frameIndex, state.speed, totalFrames]);

  useEffect(() => {
    const handleVisibility = () => {
      if (document.visibilityState === "hidden") dispatch({ type: "PAUSE" });
    };

    document.addEventListener("visibilitychange", handleVisibility);
    return () => document.removeEventListener("visibilitychange", handleVisibility);
  }, []);

  return {
    state,
    play: () => {
      if (!prefersReducedMotion) dispatch({ type: "PLAY" });
    },
    pause: () => dispatch({ type: "PAUSE" }),
    replay: () => {
      if (!prefersReducedMotion) dispatch({ type: "REPLAY" });
    },
    skip: () => dispatch({ type: "SKIP" }),
    goToFrame: (frameIndex) => dispatch({ type: "USER_FRAME", frameIndex }),
    setEdgeWeight: (value) => dispatch({ type: "SET_EDGE_WEIGHT", value }),
    setSpeed: (value) => dispatch({ type: "SET_SPEED", value }),
  };
}
