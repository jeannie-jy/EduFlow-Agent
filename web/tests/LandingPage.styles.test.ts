import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const landingStyles = readFileSync(resolve("src/styles/globals.css"), "utf8");

function mediaBlock(start: string, end: string) {
  const from = landingStyles.indexOf(start);
  const to = landingStyles.indexOf(end, from + start.length);
  expect(from).toBeGreaterThanOrEqual(0);
  expect(to).toBeGreaterThan(from);
  return landingStyles.slice(from, to);
}

describe("LandingPage stylesheet contract", () => {
  it("reserves a desktop viewport chapter while keeping the demo responsive", () => {
    const desktop = mediaBlock("@media (min-width: 901px) {", "@media (min-width: 901px) and (max-height: 820px)");

    expect(desktop).toMatch(/\.landing-hero\s*\{[\s\S]*?min-height:\s*calc\(100svh\s*-\s*4\.375rem\)/);
    expect(desktop).toMatch(/\.landing-hero__content\s*\{[\s\S]*?padding-top:\s*clamp\(1rem,\s*2\.4svh,\s*1\.8rem\)/);
    expect(desktop).toMatch(/\.dijkstra-demo__graph\s*\{[\s\S]*?min-height:\s*clamp\(12rem,\s*34svh,\s*24rem\)/);
    expect(desktop).toMatch(/\.demo-status-table\s*\{\s*padding:\s*0\.35rem 0\.55rem/);
    expect(desktop).toMatch(/\.demo-timeline__track\s*\{\s*margin-top:\s*0\.3rem/);

    expect(landingStyles).toContain("margin-inline: clamp(-1.5rem, -1.75vw, -0.25rem);");
    expect(landingStyles).toMatch(/#product,\s*#examples,\s*#audiences,\s*#templates\s*\{\s*scroll-margin-top:/);
  });

  it("compacts short desktop viewports without clipping and releases constraints on mobile", () => {
    const shortDesktop = mediaBlock("@media (min-width: 901px) and (max-height: 820px) {", "@media (max-width: 900px)");
    const mobile = mediaBlock("@media (max-width: 900px)", "@media (max-width: 680px)");

    expect(shortDesktop).toMatch(/\.landing-hero__content\s*\{\s*padding-top:\s*0\.75rem/);
    expect(shortDesktop).toMatch(/\.landing-hero__examples\s*\{\s*margin-top:\s*0\.4rem/);
    expect(shortDesktop).toMatch(/\.dijkstra-demo__graph\s*\{\s*min-height:\s*10rem/);

    expect(mobile).toMatch(/\.landing-hero\s*\{\s*display:\s*block/);
    expect(mobile).not.toMatch(/\.landing-hero\s*\{[^}]*\b(?:min-)?height:/);
    expect(landingStyles).not.toMatch(/\.landing-hero\s*\{[^}]*overflow:\s*hidden/);
  });
});
