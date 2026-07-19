import type { CSSProperties } from "react";
import { AnimatedGridPattern } from "@/components/ui/animated-grid-pattern";

const themeGridStyle = {
  "--workspace-grid-fill": "color-mix(in oklch, var(--primary) 11%, transparent)",
  "--workspace-grid-stroke": "var(--border)",
} as CSSProperties;

export function WorkspaceGrid() {
  const canAnimate = typeof ResizeObserver !== "undefined";

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
      {canAnimate ? (
        <AnimatedGridPattern
          className="motion-reduce:hidden opacity-55"
          duration={6}
          maxOpacity={0.28}
          numSquares={24}
          style={{
            fill: "var(--workspace-grid-fill)",
            stroke: "var(--workspace-grid-stroke)",
          }}
        />
      ) : null}
    </div>
  );
}
