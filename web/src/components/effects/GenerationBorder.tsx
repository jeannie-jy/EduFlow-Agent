import { useEffect, useState } from "react";
import type { GenerationState } from "@/components/workbench/AiStatusStrip";

type GenerationBorderProps = {
  generation: GenerationState;
};

export function GenerationBorder({ generation }: GenerationBorderProps) {
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(
    () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );

  useEffect(() => {
    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const syncPreference = () => setPrefersReducedMotion(mediaQuery.matches);
    mediaQuery.addEventListener?.("change", syncPreference);
    return () => mediaQuery.removeEventListener?.("change", syncPreference);
  }, []);

  if (generation !== "planning") {
    return null;
  }

  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 rounded-[inherit] overflow-hidden">
      <div className="absolute inset-0 rounded-[inherit] border border-primary/45" />
      {!prefersReducedMotion && (
        <div
          className="absolute inset-0 rounded-[inherit]"
          style={{
            background: "conic-gradient(from 0deg, transparent 70%, var(--primary) 85%, var(--ring) 100%)",
            animation: "generation-border-spin 4s linear infinite",
          }}
        />
      )}
    </div>
  );
}