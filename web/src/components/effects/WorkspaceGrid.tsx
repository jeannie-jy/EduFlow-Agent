import { lazy, Suspense, useEffect, useState, type CSSProperties } from "react";

const DeferredAnimatedGridPattern = lazy(async () => {
  const module = await import("./magicui/animated-grid-pattern");
  return { default: module.AnimatedGridPattern };
});

const themeGridStyle = {
  "--workspace-grid-fill": "color-mix(in oklch, var(--primary) 11%, transparent)",
  "--workspace-grid-stroke": "var(--border)",
} as CSSProperties;

export function WorkspaceGrid() {
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(
    () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  const [shouldLoadAnimation, setShouldLoadAnimation] = useState(false);

  useEffect(() => {
    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const syncPreference = () => setPrefersReducedMotion(mediaQuery.matches);

    mediaQuery.addEventListener?.("change", syncPreference);
    return () => mediaQuery.removeEventListener?.("change", syncPreference);
  }, []);

  useEffect(() => {
    if (prefersReducedMotion || typeof ResizeObserver === "undefined") {
      return;
    }

    let cancelled = false;
    const loadAnimation = () => {
      if (!cancelled) {
        setShouldLoadAnimation(true);
      }
    };
    const idleWindow = window as typeof window & {
      cancelIdleCallback?: (handle: number) => void;
      requestIdleCallback?: (callback: () => void) => number;
    };
    const idleHandle = idleWindow.requestIdleCallback?.(loadAnimation);
    const timeoutHandle = idleHandle === undefined ? window.setTimeout(loadAnimation, 0) : undefined;

    return () => {
      cancelled = true;
      if (idleHandle !== undefined) {
        idleWindow.cancelIdleCallback?.(idleHandle);
      }
      if (timeoutHandle !== undefined) {
        window.clearTimeout(timeoutHandle);
      }
    };
  }, [prefersReducedMotion]);

  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 overflow-hidden rounded-[inherit]"
      style={themeGridStyle}
    >
      <svg
        className="absolute inset-0 size-full opacity-55"
        focusable="false"
        preserveAspectRatio="xMidYMid slice"
      >
        <defs>
          <pattern
            id="workspace-grid-static"
            width="40"
            height="40"
            patternUnits="userSpaceOnUse"
          >
            <path d="M.5 40V.5H40" fill="none" stroke="var(--workspace-grid-stroke)" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#workspace-grid-static)" />
      </svg>
      {shouldLoadAnimation && !prefersReducedMotion ? (
        <Suspense fallback={null}>
          <DeferredAnimatedGridPattern
            className="opacity-55"
            duration={6}
            maxOpacity={0.28}
            numSquares={24}
            style={{
              fill: "var(--workspace-grid-fill)",
              stroke: "var(--workspace-grid-stroke)",
            }}
          />
        </Suspense>
      ) : null}
    </div>
  );
}
