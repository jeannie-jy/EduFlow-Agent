import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const landingStyles = readFileSync(
  resolve("src/styles/globals.css"),
  "utf8",
);

describe("LandingPage stylesheet contract", () => {
  it("keeps the hero intrinsic while applying dense desktop demo rules and target offsets", () => {
    expect(landingStyles).not.toMatch(/\.landing-hero\s*\{[^}]*\b(?:min-)?height:/);
    expect(landingStyles).not.toContain("height: calc(100svh - 7rem)");
    expect(landingStyles).toContain("margin-inline: clamp(-1.5rem, -1.75vw, -0.25rem);");
    expect(landingStyles).toContain(".landing-hero__demo-plate .dijkstra-demo.dijkstra-demo--compact .dijkstra-demo__graph { min-height: 12rem; }");
    expect(landingStyles).toContain(".landing-hero__demo-plate .demo-status-table { padding: 0.35rem 0.55rem; }");
    expect(landingStyles).toContain(".landing-hero__demo-plate .demo-timeline__track { margin-top: 0.3rem; }");
    expect(landingStyles).toMatch(/#product,\s*#examples,\s*#audiences,\s*#templates \{\s*scroll-margin-top:/);
  });

  it("reserves first-viewport space for the next chapter without clipping the compact demo", () => {
    expect(landingStyles).toContain(".landing-hero__content { padding-top: 1rem; }");
    expect(landingStyles).toContain(".landing-hero__examples { margin: 0.6rem 0 0.35rem; }");
    expect(landingStyles).toContain(".landing-hero__demo-plate .dijkstra-demo { gap: 0.25rem; padding: 0.4rem 0.55rem; }");
    expect(landingStyles).toContain(".landing-hero__demo-plate .demo-status-table th,");
    expect(landingStyles).toContain(".landing-hero__demo-plate .demo-timeline__item p { font-size: 0.6rem; line-height: 1.1; }");
    expect(landingStyles).not.toMatch(/\.landing-hero\s*\{[^}]*\boverflow:\s*hidden/);
  });
});
