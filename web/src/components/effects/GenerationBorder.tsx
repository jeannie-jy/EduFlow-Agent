import { lazy, Suspense, useEffect, useState } from "react";
import type { GenerationState } from "@/components/workbench/AiStatusStrip";

const DeferredBorderBeam = lazy(async () => {
  const module = await import("./magicui/border-beam");
  return { default: module.BorderBeam };
});

type GenerationBorderProps = {
  generation: GenerationState;
};

export function GenerationBorder({ generation }: GenerationBorderProps) {
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
    if (generation !== "planning" || prefersReducedMotion) {
      setShouldLoadAnimation(false);
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
  }, [generation, prefersReducedMotion]);

  if (generation !== "planning") {
    return null;
  }

  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 rounded-[inherit]">
      <div className="absolute inset-0 rounded-[inherit] border border-primary/45" />
      {shouldLoadAnimation && !prefersReducedMotion ? (
        <Suspense fallback={null}>
          <DeferredBorderBeam
            borderWidth={2}
            colorFrom="var(--primary)"
            colorTo="var(--ring)"
            duration={6}
            size={72}
          />
        </Suspense>
      ) : null}
    </div>
  );
}
