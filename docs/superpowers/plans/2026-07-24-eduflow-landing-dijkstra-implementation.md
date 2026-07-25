# EduFlow Landing and Dijkstra Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the redesigned Light/Dark EduFlow landing page and a stable, animated, public Dijkstra experience that demonstrates the complete “understand, play, change, recompute, output” loop.

**Architecture:** Keep the landing page, public exploration route, and authenticated workspace as separate presentation layers. Reuse a deterministic Dijkstra scenario model and a shared public demo player between the Hero and `/explore/dijkstra`; keep autoplay in an interruptible reducer-driven state machine and keep theme/motion policy in application providers.

**Tech Stack:** React 18.3, TypeScript 6, Vite 8, React Router 7, Tailwind CSS 4, Base UI, Motion for React via `motion/react`, React Flow, Vitest, Testing Library.

## Global Constraints

- Theme options shown to users are exactly `跟随系统`, `Light`, and `Dark`.
- Light uses `#F3EBD8` as page background and `#25231F` as primary text.
- Dark uses `#1B1814` as page background and `#EFE4CE` as primary text.
- The public Hero must render a complete static Dijkstra state before interactive code is ready.
- Autoplay starts only after an explicit user action and must remain pausable, skippable, replayable, and interruptible.
- Any user frame jump or parameter change exits autoplay and enters explore mode.
- The first release exposes only Dijkstra edge `B-D` weight as a mutable public parameter.
- Public demo data is deterministic and must not call the LLM or project APIs.
- Motion must respect `prefers-reduced-motion`; reduced motion keeps opacity feedback but removes large transforms and autoplay.
- Do not add Three.js, shader backgrounds, continuous particles, cursor-following glow, 3D card tilt, or looping typewriter effects.
- Do not stage or commit `.gitignore`, `docs/ui-audit/`, `web/src/lib/auth.ts`, or `web/src/lib/auth.test.ts`.
- The selected visual target is `docs/design-references/eduflow-landing-interactive-manuscript.png`; where the earlier prose plan conflicts with this image, the selected image governs visual hierarchy and spacing.

## Scope Decomposition

This plan implements the first independently releasable subsystem:

1. Light/Dark design foundation.
2. New public landing page.
3. Complete deterministic Dijkstra public demo.
4. `/explore/dijkstra` route.
5. Smooth, interruptible motion and accessibility fallbacks.

Create later plans for:

- Bubble sort and Round Robin public scenarios.
- Full student player and teacher creation flow.
- Template detail pages and expanded public content.
- Cross-route shared-element polish and final production analytics.

## File Structure

Create:

```text
web/src/features/landing/landing-content.ts
web/src/features/landing/LandingPage.test.tsx
web/src/features/landing/components/SiteHeader.tsx
web/src/features/landing/components/HeroSection.tsx
web/src/features/landing/components/HowItWorksSection.tsx
web/src/features/landing/components/AudienceSection.tsx
web/src/features/landing/components/CapabilitySection.tsx
web/src/features/landing/components/TemplateSection.tsx
web/src/features/landing/components/FinalActionSection.tsx
web/src/features/explore/DijkstraExplorePage.tsx
web/src/features/explore/DijkstraExplorePage.test.tsx
web/src/features/demo/demo-types.ts
web/src/features/demo/demo-reducer.ts
web/src/features/demo/demo-reducer.test.ts
web/src/features/demo/useDemoPlayback.ts
web/src/features/demo/DijkstraDemo.tsx
web/src/features/demo/DijkstraDemo.test.tsx
web/src/features/demo/DemoStatusTable.tsx
web/src/features/demo/DemoTimeline.tsx
web/src/features/demo/DemoParameterPanel.tsx
web/src/features/demo/demo-motion.ts
```

Modify:

```text
web/package.json
web/package-lock.json
web/index.html
web/src/app/AppProviders.tsx
web/src/app/router.tsx
web/src/app/router.test.tsx
web/src/components/layout/ThemeSwitcher.tsx
web/src/components/ui/button.tsx
web/src/components/workbench/SimulationGraph.tsx
web/src/components/workbench/simulation-model.ts
web/src/components/workbench/simulation-model.test.ts
web/src/features/landing/LandingPage.tsx
web/src/styles/globals.css
web/src/test/setup.ts
web/src/theme/theme.ts
web/src/theme/theme-script.ts
web/src/theme/ThemeProvider.tsx
web/src/theme/theme.test.tsx
```

---

### Task 1: Add Motion and system-aware theme preference

**Files:**
- Modify: `web/package.json`
- Modify: `web/package-lock.json`
- Modify: `web/src/theme/theme.ts`
- Modify: `web/src/theme/theme-script.ts`
- Modify: `web/index.html`
- Modify: `web/src/theme/ThemeProvider.tsx`
- Modify: `web/src/theme/theme.test.tsx`
- Modify: `web/src/components/layout/ThemeSwitcher.tsx`
- Modify: `web/src/app/AppProviders.tsx`

**Interfaces:**
- Produces: `ThemePreference = "system" | "light" | "dark"`
- Produces: `resolveTheme(preference: ThemePreference, prefersDark: boolean): ThemeId`
- Produces: `useTheme(): { preference, resolvedTheme, setPreference }`
- Produces: application-wide `<MotionConfig reducedMotion="user">`

- [ ] **Step 1: Install Motion**

Run:

```powershell
cd web
npm install motion
```

Expected: `motion` appears in `dependencies`, and `package-lock.json` changes without peer-dependency errors.

- [ ] **Step 2: Replace theme tests with system-aware expectations**

Use these cases in `web/src/theme/theme.test.tsx`:

```tsx
it("resolves system preference before explicit selection", () => {
  window.matchMedia = createMatchMedia(true);
  const { result } = renderHook(() => useTheme(), { wrapper: ThemeProvider });
  expect(result.current.preference).toBe("system");
  expect(result.current.resolvedTheme).toBe("dark");
  expect(document.documentElement.dataset.theme).toBe("dark");
});

it("persists an explicit Light selection", async () => {
  window.matchMedia = createMatchMedia(true);
  function Probe() {
    const { preference, resolvedTheme, setPreference } = useTheme();
    return (
      <>
        <span>{preference}:{resolvedTheme}</span>
        <button onClick={() => setPreference("light")}>Light</button>
      </>
    );
  }
  render(<ThemeProvider><Probe /></ThemeProvider>);
  await userEvent.click(screen.getByRole("button", { name: "Light" }));
  expect(screen.getByText("light:light")).toBeVisible();
  expect(localStorage.getItem("eduflow-theme")).toBe("light");
  expect(document.documentElement.dataset.theme).toBe("light");
});

it("keeps the pre-hydration script aligned with its exported source", () => {
  const inlineScript = indexHtml.match(/<script>([\s\S]*?)<\/script>/)?.[1] ?? "";
  const normalize = (value: string) => value.replace(/\s+/g, "");
  expect(normalize(inlineScript)).toBe(normalize(themeScript));
});
```

Add this helper at the top of that test file:

```ts
function createMatchMedia(matches: boolean) {
  return (query: string) =>
    ({
      matches,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList;
}
```

- [ ] **Step 3: Run the theme tests and verify failure**

Run:

```powershell
cd web
npm test -- src/theme/theme.test.tsx
```

Expected: FAIL because the existing context has `theme/setTheme`, defaults to Light, and cannot resolve `system`.

- [ ] **Step 4: Implement the preference and resolved theme model**

Replace `web/src/theme/theme.ts` with:

```ts
export const THEMES = [
  { id: "system", label: "跟随系统" },
  { id: "light", label: "Light" },
  { id: "dark", label: "Dark" },
] as const;

export type ThemePreference = (typeof THEMES)[number]["id"];
export type ThemeId = Exclude<ThemePreference, "system">;

export const THEME_STORAGE_KEY = "eduflow-theme";
export const DARK_MEDIA_QUERY = "(prefers-color-scheme: dark)";

export const isThemePreference = (value: string | null): value is ThemePreference =>
  THEMES.some((theme) => theme.id === value);

export function resolveInitialPreference(): ThemePreference {
  const saved = localStorage.getItem(THEME_STORAGE_KEY);
  return isThemePreference(saved) ? saved : "system";
}

export function resolveTheme(
  preference: ThemePreference,
  prefersDark: boolean,
): ThemeId {
  return preference === "system" ? (prefersDark ? "dark" : "light") : preference;
}
```

Replace `web/src/theme/ThemeProvider.tsx` with:

```tsx
import {
  createContext, useContext, useEffect, useMemo, useState, type PropsWithChildren,
} from "react";
import {
  DARK_MEDIA_QUERY, resolveInitialPreference, resolveTheme,
  THEME_STORAGE_KEY, type ThemeId, type ThemePreference,
} from "./theme";

type ThemeContextValue = {
  preference: ThemePreference;
  resolvedTheme: ThemeId;
  setPreference: (theme: ThemePreference) => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: PropsWithChildren) {
  const [preference, setPreference] = useState(resolveInitialPreference);
  const [prefersDark, setPrefersDark] = useState(
    () => window.matchMedia(DARK_MEDIA_QUERY).matches,
  );
  const resolvedTheme = resolveTheme(preference, prefersDark);

  useEffect(() => {
    const media = window.matchMedia(DARK_MEDIA_QUERY);
    const update = (event: MediaQueryListEvent) => setPrefersDark(event.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = resolvedTheme;
    localStorage.setItem(THEME_STORAGE_KEY, preference);
  }, [preference, resolvedTheme]);

  const value = useMemo(
    () => ({ preference, resolvedTheme, setPreference }),
    [preference, resolvedTheme],
  );
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const value = useContext(ThemeContext);
  if (!value) throw new Error("useTheme must be used inside ThemeProvider");
  return value;
}
```

Set `web/src/theme/theme-script.ts` to:

```ts
export const themeScript = `(()=>{try{const k="eduflow-theme",v=localStorage.getItem(k),p=["light","dark","system"].includes(v||"")?v:"system",d=matchMedia("(prefers-color-scheme: dark)").matches,t=p==="system"?(d?"dark":"light"):p;document.documentElement.dataset.theme=t}catch{document.documentElement.dataset.theme="light"}})();`;
```

Copy that exact script body into the inline `<script>` in `web/index.html`.

- [ ] **Step 5: Update the switcher and application providers**

Replace `ThemeSwitcher` with:

```tsx
import { MonitorIcon, MoonIcon, SunIcon } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuLabel,
  DropdownMenuRadioGroup, DropdownMenuRadioItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { THEMES, isThemePreference, type ThemePreference } from "@/theme/theme";
import { useTheme } from "@/theme/ThemeProvider";

const icons: Record<ThemePreference, typeof SunIcon> = {
  system: MonitorIcon,
  light: SunIcon,
  dark: MoonIcon,
};

export function ThemeSwitcher() {
  const { preference, resolvedTheme, setPreference } = useTheme();
  const current = THEMES.find(({ id }) => id === preference) ?? THEMES[0];
  const CurrentIcon = icons[preference];
  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger
          className={buttonVariants({ variant: "outline", size: "icon" })}
          aria-label={`主题：${current.label}`}
        >
          <CurrentIcon aria-hidden="true" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuRadioGroup
            value={preference}
            onValueChange={(value) => {
              if (isThemePreference(value)) setPreference(value);
            }}
          >
            <DropdownMenuLabel>外观</DropdownMenuLabel>
            {THEMES.map(({ id, label }) => {
              const Icon = icons[id];
              return (
                <DropdownMenuRadioItem key={id} value={id} closeOnClick>
                  <Icon aria-hidden="true" />
                  {label}
                </DropdownMenuRadioItem>
              );
            })}
          </DropdownMenuRadioGroup>
        </DropdownMenuContent>
      </DropdownMenu>
      <span className="sr-only" aria-live="polite" aria-atomic="true">
        当前主题：{current.label}，实际显示：{resolvedTheme}
      </span>
    </>
  );
}
```

Wrap children in `AppProviders` as:

```tsx
import { MotionConfig } from "motion/react";

<ThemeProvider>
  <MotionConfig reducedMotion="user">
    <TooltipProvider>{children}</TooltipProvider>
  </MotionConfig>
</ThemeProvider>
```

Import `MotionConfig` from `"motion/react"`.

- [ ] **Step 6: Run theme tests**

Run:

```powershell
cd web
npm test -- src/theme/theme.test.tsx src/components/layout/AppShell.test.tsx
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add web/package.json web/package-lock.json web/index.html web/src/theme web/src/components/layout/ThemeSwitcher.tsx web/src/app/AppProviders.tsx
git commit -m "feat: add system-aware themes and motion policy"
```

---

### Task 2: Replace generic colors with the paper and study design tokens

**Files:**
- Modify: `web/src/styles/globals.css`
- Modify: `web/src/components/ui/button.tsx`
- Test: `web/src/theme/theme.test.tsx`

**Interfaces:**
- Consumes: `data-theme="light" | "dark"`
- Produces: semantic CSS tokens for page, surface, brand, interaction, progress, canvas, and motion

- [ ] **Step 1: Add a token presence test**

Append to `web/src/theme/theme.test.tsx`:

```tsx
it("ships the required Light and Dark semantic tokens", () => {
  const css = readFileSync(new URL("../styles/globals.css", import.meta.url), "utf8");
  expect(css).toContain("--paper-texture-opacity");
  expect(css).toContain("--canvas-background");
  expect(css).toContain("--motion-layout");
  expect(css).toContain("#F3EBD8");
  expect(css).toContain("#1B1814");
});
```

Import `readFileSync` from `"node:fs"`.

- [ ] **Step 2: Run the test and verify failure**

Run:

```powershell
cd web
npm test -- src/theme/theme.test.tsx
```

Expected: FAIL because the paper/study tokens are absent.

- [ ] **Step 3: Replace theme token values**

In `globals.css`, map existing component tokens to the approved palettes and add:

```css
:root,
html[data-theme="light"] {
  color-scheme: light;
  --background: #F3EBD8;
  --foreground: #25231F;
  --card: #FFF8E8;
  --card-foreground: #25231F;
  --popover: #FFF8E8;
  --popover-foreground: #25231F;
  --primary: #8B3A32;
  --primary-foreground: #FFF8E8;
  --secondary: #ECE1C8;
  --secondary-foreground: #25231F;
  --muted: #E8DDC4;
  --muted-foreground: #686052;
  --accent: #DDE5D8;
  --accent-foreground: #315E59;
  --destructive: #A8463A;
  --border: #CFC2A5;
  --input: #BEB092;
  --ring: #315E59;
  --success: #54755B;
  --warning: #B67A2B;
  --interactive: #315E59;
  --progress: #B67A2B;
  --canvas-background: #EEE4CE;
  --canvas-grid: #D5C8AC;
  --graph-line: #8B806C;
  --graph-active: #315E59;
  --graph-settled: #54755B;
  --stage-bg: var(--canvas-background);
  --stage-dot: var(--canvas-grid);
  --paper-texture-opacity: 0.035;
}

html[data-theme="dark"] {
  color-scheme: dark;
  --background: #1B1814;
  --foreground: #EFE4CE;
  --card: #24201B;
  --card-foreground: #EFE4CE;
  --popover: #2E2922;
  --popover-foreground: #EFE4CE;
  --primary: #D58A78;
  --primary-foreground: #1B1814;
  --secondary: #2E2922;
  --secondary-foreground: #EFE4CE;
  --muted: #342E26;
  --muted-foreground: #BEB29E;
  --accent: #263631;
  --accent-foreground: #70A59A;
  --destructive: #E18478;
  --border: #4B4337;
  --input: #5A5041;
  --ring: #70A59A;
  --success: #7AA184;
  --warning: #D6AA5F;
  --interactive: #70A59A;
  --progress: #D6AA5F;
  --canvas-background: #171512;
  --canvas-grid: #353028;
  --graph-line: #827663;
  --graph-active: #70A59A;
  --graph-settled: #7AA184;
  --stage-bg: var(--canvas-background);
  --stage-dot: var(--canvas-grid);
  --paper-texture-opacity: 0.018;
}
```

Add global motion variables:

```css
:root {
  --motion-instant: 140ms;
  --motion-control: 200ms;
  --motion-panel: 280ms;
  --motion-layout: 380ms;
  --ease-enter: cubic-bezier(0.22, 1, 0.36, 1);
  --ease-exit: cubic-bezier(0.4, 0, 1, 1);
  --ease-layout: cubic-bezier(0.65, 0, 0.35, 1);
}
```

Remove the desktop rule that forces `body` and `#root` to `height: 100svh; overflow: hidden;`. Long public pages must scroll; keep workspace overflow inside `AppShell`.

- [ ] **Step 4: Add restrained interaction primitives**

Add:

```css
.paper-surface {
  border: 1px solid var(--border);
  background: var(--card);
  box-shadow: 0 2px 0 color-mix(in srgb, var(--foreground) 7%, transparent);
}

.interactive-lift {
  transition:
    transform var(--motion-control) var(--ease-enter),
    border-color var(--motion-control) var(--ease-enter),
    box-shadow var(--motion-control) var(--ease-enter);
}

@media (hover: hover) {
  .interactive-lift:hover {
    transform: translateY(-2px);
    border-color: color-mix(in srgb, var(--interactive) 42%, var(--border));
    box-shadow: 0 4px 0 color-mix(in srgb, var(--foreground) 8%, transparent);
  }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    scroll-behavior: auto !important;
    animation-duration: 1ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 1ms !important;
  }
}
```

Update `buttonVariants` so the base class includes `active:not-aria-[haspopup]:scale-[0.98]` and uses the shared motion duration.

- [ ] **Step 5: Run tests and build**

Run:

```powershell
cd web
npm test -- src/theme/theme.test.tsx
npm run build
```

Expected: both commands PASS.

- [ ] **Step 6: Commit**

```powershell
git add web/src/styles/globals.css web/src/components/ui/button.tsx web/src/theme/theme.test.tsx
git commit -m "feat: add EduFlow paper and study design tokens"
```

---

### Task 3: Make the Dijkstra model recomputable with a public edge parameter

**Files:**
- Modify: `web/src/components/workbench/simulation-model.ts`
- Modify: `web/src/components/workbench/simulation-model.test.ts`
- Modify: `web/src/components/workbench/SimulationGraph.tsx`

**Interfaces:**
- Produces: `DijkstraScenario`
- Produces: `buildDijkstraScenario(options?: { edgeOverrides?: Partial<Record<string, number>> }): DijkstraScenario`
- Preserves: `buildDijkstraFrames(): SimulationFrame[]`
- Updates: `SimulationGraph({ frame, edges?, compact? })`

- [ ] **Step 1: Write failing recomputation tests**

Append:

```ts
it("recomputes frames and graph labels after changing B-D weight", () => {
  const scenario = buildDijkstraScenario({ edgeOverrides: { "B-D": 3 } });
  expect(scenario.edges.find((edge) => edge.id === "B-D")?.weight).toBe(3);
  expect(scenario.frames.at(-1)?.distances.D).toBe(5);
  expect(scenario.frames.at(-1)?.predecessors.D).toBe("B");
});

it("does not mutate the default scenario", () => {
  const changed = buildDijkstraScenario({ edgeOverrides: { "B-D": 3 } });
  const original = buildDijkstraScenario();
  expect(changed.edges).not.toBe(original.edges);
  expect(original.edges.find((edge) => edge.id === "B-D")?.weight).toBe(7);
  expect(original.frames.at(-1)?.distances.D).toBe(9);
});
```

Import `buildDijkstraScenario`.

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
cd web
npm test -- src/components/workbench/simulation-model.test.ts
```

Expected: FAIL because `buildDijkstraScenario` does not exist.

- [ ] **Step 3: Implement the scenario builder**

Add:

```ts
export type DijkstraScenario = {
  edges: GraphEdgeSpec[];
  frames: SimulationFrame[];
};

export type DijkstraScenarioOptions = {
  edgeOverrides?: Partial<Record<string, number>>;
};

export function buildDijkstraScenario(
  options: DijkstraScenarioOptions = {},
): DijkstraScenario {
  const edges = graphEdges.map((edge) => ({
    ...edge,
    weight: options.edgeOverrides?.[edge.id] ?? edge.weight,
  }));
  return { edges, frames: buildFramesFromEdges(edges) };
}
```

Rename the existing frame-building body to:

```ts
function buildFramesFromEdges(edges: GraphEdgeSpec[]): SimulationFrame[]
```

Make its adjacency builder consume the passed `edges`. Keep:

```ts
export function buildDijkstraFrames(): SimulationFrame[] {
  return buildDijkstraScenario().frames;
}

export const simulationFrames = buildDijkstraFrames();
```

- [ ] **Step 4: Allow graph edge injection**

Update `SimulationGraph` props:

```ts
type SimulationGraphProps = {
  frame: SimulationFrame;
  edges?: GraphEdgeSpec[];
  compact?: boolean;
};

export function SimulationGraph({
  frame,
  edges = graphEdges,
  compact = false,
}: SimulationGraphProps) {
```

Replace internal `graphEdges.map` calls with `edges.map`, and include `edges` in memo dependencies.

- [ ] **Step 5: Run tests**

Run:

```powershell
cd web
npm test -- src/components/workbench/simulation-model.test.ts
npm run typecheck
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add web/src/components/workbench/simulation-model.ts web/src/components/workbench/simulation-model.test.ts web/src/components/workbench/SimulationGraph.tsx
git commit -m "feat: support deterministic Dijkstra recomputation"
```

---

### Task 4: Implement the interruptible demo state machine

**Files:**
- Create: `web/src/features/demo/demo-types.ts`
- Create: `web/src/features/demo/demo-reducer.ts`
- Create: `web/src/features/demo/demo-reducer.test.ts`
- Create: `web/src/features/demo/useDemoPlayback.ts`
- Create: `web/src/features/demo/demo-motion.ts`
- Modify: `web/src/test/setup.ts`

**Interfaces:**
- Produces: `DemoMode = "poster" | "autoplay" | "paused" | "explore" | "completed"`
- Produces: `demoReducer(state: DemoState, event: DemoEvent): DemoState`
- Produces: `useDemoPlayback(options): DemoPlaybackController`
- Produces: shared Motion variants in `demo-motion.ts`

- [ ] **Step 1: Write reducer tests**

Create tests covering:

```ts
it("starts only after PLAY", () => {
  expect(demoReducer(initialDemoState, { type: "PLAY" })).toMatchObject({
    mode: "autoplay",
    frameIndex: 0,
  });
});

it("hands control to explore after a user frame jump", () => {
  const playing = { ...initialDemoState, mode: "autoplay" as const };
  expect(demoReducer(playing, { type: "USER_FRAME", frameIndex: 5 })).toMatchObject({
    mode: "explore",
    frameIndex: 5,
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

it("uses poster mode when reduced motion is requested", () => {
  const playing = { ...initialDemoState, mode: "autoplay" as const };
  expect(demoReducer(playing, { type: "REDUCE_MOTION" }).mode).toBe("poster");
});
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
cd web
npm test -- src/features/demo/demo-reducer.test.ts
```

Expected: FAIL because reducer files do not exist.

- [ ] **Step 3: Implement types and reducer**

Use:

```ts
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
```

Implement every event as a pure reducer:

```ts
export function demoReducer(state: DemoState, event: DemoEvent): DemoState {
  switch (event.type) {
    case "PLAY":
      return { ...state, mode: "autoplay" };
    case "PAUSE":
      return state.mode === "autoplay" ? { ...state, mode: "paused" } : state;
    case "TICK": {
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
```

- [ ] **Step 4: Implement the playback hook**

Use:

```ts
import { useEffect, useReducer } from "react";
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

export function useDemoPlayback(totalFrames: number): DemoPlaybackController {
  const [state, dispatch] = useReducer(demoReducer, initialDemoState);
  const reduceMotion = useReducedMotion();

  useEffect(() => {
    if (reduceMotion) dispatch({ type: "REDUCE_MOTION" });
  }, [reduceMotion]);

  useEffect(() => {
    if (state.mode !== "autoplay") return;
    const timer = window.setTimeout(
      () => dispatch({ type: "TICK", totalFrames }),
      1400 / state.speed,
    );
    return () => window.clearTimeout(timer);
  }, [state.mode, state.frameIndex, state.speed, totalFrames]);

  useEffect(() => {
    const handleVisibility = () => {
      if (document.visibilityState === "hidden") dispatch({ type: "PAUSE" });
    };
    document.addEventListener("visibilitychange", handleVisibility);
    return () => document.removeEventListener("visibilitychange", handleVisibility);
  }, []);

  return {
    state,
    play: () => dispatch({ type: "PLAY" }),
    pause: () => dispatch({ type: "PAUSE" }),
    replay: () => dispatch({ type: "REPLAY" }),
    skip: () => dispatch({ type: "SKIP" }),
    goToFrame: (frameIndex) => dispatch({ type: "USER_FRAME", frameIndex }),
    setEdgeWeight: (value) => dispatch({ type: "SET_EDGE_WEIGHT", value }),
    setSpeed: (value) => dispatch({ type: "SET_SPEED", value }),
  };
}
```

- [ ] **Step 5: Define shared motion variants**

In `demo-motion.ts` export:

```ts
export const reveal = {
  hidden: { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0 },
};

export const shortCrossfade = {
  initial: { opacity: 0, y: 6 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -4 },
};

export const enterTransition = {
  duration: 0.28,
  ease: [0.22, 1, 0.36, 1] as const,
};
```

- [ ] **Step 6: Run tests**

Run:

```powershell
cd web
npm test -- src/features/demo/demo-reducer.test.ts
npm run typecheck
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add web/src/features/demo web/src/test/setup.ts
git commit -m "feat: add interruptible public demo state machine"
```

---

### Task 5: Build the reusable animated Dijkstra demo

**Files:**
- Create: `web/src/features/demo/DijkstraDemo.tsx`
- Create: `web/src/features/demo/DijkstraDemo.test.tsx`
- Create: `web/src/features/demo/DemoStatusTable.tsx`
- Create: `web/src/features/demo/DemoTimeline.tsx`
- Create: `web/src/features/demo/DemoParameterPanel.tsx`
- Modify: `web/src/styles/globals.css`

**Interfaces:**
- Consumes: `buildDijkstraScenario`
- Consumes: `useDemoPlayback`
- Produces: `<DijkstraDemo compact?: boolean autoFocusControls?: boolean />`

- [ ] **Step 1: Write interaction tests**

Test:

```tsx
it("starts from a complete poster and only autoplays after activation", async () => {
  renderPage(<DijkstraDemo compact />);
  expect(screen.getByText("设置源点")).toBeVisible();
  expect(screen.getByRole("button", { name: "观看 60 秒演示" })).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "观看 60 秒演示" }));
  expect(screen.getByRole("button", { name: "暂停演示" })).toBeVisible();
});

it("changes B-D weight and exposes the recomputed distance", async () => {
  renderPage(<DijkstraDemo />);
  const input = screen.getByRole("slider", { name: "B 到 D 的边权重" });
  fireEvent.change(input, { target: { value: "3" } });
  expect(await screen.findByText("D 的最短距离变为 5")).toBeVisible();
  expect(screen.getByText("自由体验")).toBeVisible();
});

it("a timeline jump exits autoplay", async () => {
  renderPage(<DijkstraDemo />);
  await userEvent.click(screen.getByRole("button", { name: "观看 60 秒演示" }));
  await userEvent.click(screen.getByRole("button", { name: "跳到第 6 帧" }));
  expect(screen.getByText("自由体验")).toBeVisible();
});
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
cd web
npm test -- src/features/demo/DijkstraDemo.test.tsx
```

Expected: FAIL because the component does not exist.

- [ ] **Step 3: Implement the component composition**

`DijkstraDemo` must:

1. call `useDemoPlayback`;
2. memoize `buildDijkstraScenario({ edgeOverrides: { "B-D": state.edgeWeight } })`;
3. select `scenario.frames[state.frameIndex]`;
4. render `SimulationGraph` with `scenario.edges`;
5. render `DemoStatusTable`, `DemoTimeline`, and `DemoParameterPanel`;
6. wrap narration changes in `AnimatePresence mode="wait"`;
7. expose poster/play/pause/replay/skip controls with accessible names;
8. render `compact` without the parameter panel but retain timeline and narration.

Use this public status copy:

```ts
const modeLabels = {
  poster: "准备体验",
  autoplay: "自动演示",
  paused: "演示已暂停",
  explore: "自由体验",
  completed: "演示完成",
} as const;
```

For the changed edge result, render:

```tsx
{state.edgeWeight === 3 && (
  <p role="status">D 的最短距离变为 5</p>
)}
```

- [ ] **Step 4: Add animation classes for graph state changes**

Add one-shot transitions for `.simulation-flow-node`, edge stroke, table cell flash, timeline cursor, and narration. Do not add infinite animation. Guard transform-heavy behavior inside:

```css
@media (prefers-reduced-motion: no-preference) { ... }
```

- [ ] **Step 5: Run focused tests**

Run:

```powershell
cd web
npm test -- src/features/demo/DijkstraDemo.test.tsx src/components/workbench/simulation-model.test.ts
npm run typecheck
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add web/src/features/demo web/src/styles/globals.css
git commit -m "feat: build animated Dijkstra public demo"
```

---

### Task 6: Build the redesigned header and Hero

**Files:**
- Create: `web/src/features/landing/landing-content.ts`
- Create: `web/src/features/landing/components/SiteHeader.tsx`
- Create: `web/src/features/landing/components/HeroSection.tsx`
- Create: `web/src/features/landing/LandingPage.test.tsx`
- Modify: `web/src/features/landing/LandingPage.tsx`

**Interfaces:**
- Consumes: `DijkstraDemo compact`
- Produces: semantic section anchors `product`, `examples`, `audiences`, `templates`

- [ ] **Step 1: Write the landing contract test**

```tsx
it("explains the product and exposes public and creation paths", () => {
  renderPage(<LandingPage />);
  expect(screen.getByRole("heading", {
    name: "让抽象知识，变成可以亲手操控的推演",
  })).toBeVisible();
  expect(screen.getByRole("link", { name: "体验交互推演" }))
    .toHaveAttribute("href", "/explore/dijkstra");
  expect(screen.getByRole("link", { name: "创建新的推演" }))
    .toHaveAttribute("href", "/app/new");
  expect(screen.getByRole("navigation", { name: "主导航" })).toBeVisible();
  expect(screen.getByLabelText(/主题/)).toBeVisible();
});
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
cd web
npm test -- src/features/landing/LandingPage.test.tsx
```

Expected: FAIL against the old centered SaaS landing page.

- [ ] **Step 3: Create the header**

`SiteHeader` must include:

- linked `EduFlowBrand`;
- anchors for 产品原理、交互案例、使用场景、模板库;
- `ThemeSwitcher`;
- 登录 link;
- 开始创建 link;
- `aria-label="主导航"`;
- scroll state that adds a visible paper surface after 24px;
- no forced transparent blur when reduced transparency is preferred.

- [ ] **Step 4: Create the Hero**

Use the selected interactive-manuscript composition:

- a slim chapter/index rail at the left edge on wide screens;
- a wide editorial headline band across the upper content area;
- the title, explanation, and actions grouped compactly rather than centered;
- a panoramic Dijkstra simulation plate spanning the main width below the title band;
- the distance ledger integrated at the right side of the plate;
- narration and timeline integrated along the lower edge of the plate;
- the next section heading visible at the bottom of the first viewport.

On tablet and mobile, remove the chapter rail, keep the headline first, and stack the complete simulation plate below it without cropping.

Render the exact heading:

```text
让抽象知识，
变成可以亲手操控的推演
```

Render body copy:

```text
从一个知识点出发，自动生成教学计划、逐帧动画、交互参数和可导出的教学内容。
```

Use `motion` reveal variants for the text group and render `<DijkstraDemo compact />` as the panoramic interactive plate below the headline band. Do not wrap the whole Hero in a generic centered card.

- [ ] **Step 5: Replace the landing shell**

`LandingPage` initially renders:

```tsx
export function LandingPage() {
  return (
    <div className="landing-page min-h-screen bg-background text-foreground">
      <SiteHeader />
      <main>
        <HeroSection />
      </main>
    </div>
  );
}
```

- [ ] **Step 6: Run tests**

Run:

```powershell
cd web
npm test -- src/features/landing/LandingPage.test.tsx
npm run typecheck
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add web/src/features/landing
git commit -m "feat: redesign EduFlow landing header and hero"
```

---

### Task 7: Add the complete landing narrative and two audience paths

**Files:**
- Create: `web/src/features/landing/components/HowItWorksSection.tsx`
- Create: `web/src/features/landing/components/AudienceSection.tsx`
- Create: `web/src/features/landing/components/CapabilitySection.tsx`
- Create: `web/src/features/landing/components/TemplateSection.tsx`
- Create: `web/src/features/landing/components/FinalActionSection.tsx`
- Modify: `web/src/features/landing/landing-content.ts`
- Modify: `web/src/features/landing/LandingPage.tsx`
- Modify: `web/src/features/landing/LandingPage.test.tsx`

**Interfaces:**
- Produces: five-step product explanation
- Produces: exactly two audience paths, student and teacher
- Produces: capability, quality, template, and final-action sections

- [ ] **Step 1: Extend the contract test**

Add assertions:

```tsx
expect(screen.getByRole("heading", { name: "从一个问题，到一场完整推演" })).toBeVisible();
expect(screen.getByRole("heading", { name: "我想理解一个知识点" })).toBeVisible();
expect(screen.getByRole("heading", { name: "我想创建教学推演" })).toBeVisible();
expect(screen.queryByText("助教")).not.toBeInTheDocument();
expect(screen.getByRole("heading", { name: "教学内容值得被认真校对" })).toBeVisible();
expect(screen.getByRole("heading", { name: "不必从空白开始" })).toBeVisible();
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
cd web
npm test -- src/features/landing/LandingPage.test.tsx
```

Expected: FAIL because the narrative sections do not exist.

- [ ] **Step 3: Add content data**

Define exact arrays:

```ts
export const processSteps = [
  ["理解知识", "识别学习目标、先修知识和常见误区"],
  ["规划教学", "安排从直觉、实例到总结的教学顺序"],
  ["生成推演", "把知识变化组织成连续、可操作的帧"],
  ["检查质量", "检查知识正确性、状态连续性和教学清晰度"],
  ["输出成果", "生成交互页面、讲解文本、字幕和视频"],
] as const;

export const templates = [
  ["Dijkstra", "图算法", "14 帧", "约 6 分钟"],
  ["冒泡排序", "数据结构", "12 帧", "约 4 分钟"],
  ["Round Robin", "操作系统", "16 帧", "约 7 分钟"],
] as const;
```

- [ ] **Step 4: Implement the five sections**

Each section must:

- use a real heading and explanatory copy;
- use `motion` only for one-shot in-view reveal;
- set `viewport={{ once: true, amount: 0.2 }}`;
- use `interactive-lift` only on actionable cards;
- avoid icon-only capability cards;
- preserve a complete static layout when JavaScript motion is reduced.

`AudienceSection` renders exactly:

```text
学生：我想理解一个知识点
教师：我想创建教学推演
```

Student CTA points to `/explore/dijkstra`; teacher CTA points to `/app/new`.

- [ ] **Step 5: Compose the full page**

Order:

```tsx
<HeroSection />
<HowItWorksSection />
<AudienceSection />
<CapabilitySection />
<TemplateSection />
<FinalActionSection />
```

Keep a semantic footer with brand and copyright.

- [ ] **Step 6: Run tests**

Run:

```powershell
cd web
npm test -- src/features/landing/LandingPage.test.tsx
npm run build
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add web/src/features/landing
git commit -m "feat: add EduFlow landing narrative and audience paths"
```

---

### Task 8: Add the full `/explore/dijkstra` experience

**Files:**
- Create: `web/src/features/explore/DijkstraExplorePage.tsx`
- Create: `web/src/features/explore/DijkstraExplorePage.test.tsx`
- Modify: `web/src/app/router.tsx`
- Modify: `web/src/app/router.test.tsx`

**Interfaces:**
- Consumes: `<DijkstraDemo />`
- Produces: public route `/explore/dijkstra`

- [ ] **Step 1: Add route tests**

Add `["/explore/dijkstra", "Dijkstra 最短路径交互推演"]` to the router cases.

Create page test:

```tsx
it("offers a complete public experience without authentication", () => {
  renderPage(<DijkstraExplorePage />);
  expect(screen.getByRole("heading", {
    name: "Dijkstra 最短路径交互推演",
  })).toBeVisible();
  expect(screen.getByRole("button", { name: "观看 60 秒演示" })).toBeVisible();
  expect(screen.getByRole("slider", { name: "B 到 D 的边权重" })).toBeVisible();
  expect(screen.getByRole("link", { name: "基于这个案例创建" }))
    .toHaveAttribute("href", "/app/new?template=dijkstra");
});
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
cd web
npm test -- src/app/router.test.tsx src/features/explore/DijkstraExplorePage.test.tsx
```

Expected: FAIL because the page and route do not exist.

- [ ] **Step 3: Implement the page**

Page structure:

```tsx
<SiteHeader />
<main>
  <header>
    <p>公开交互案例</p>
    <h1>Dijkstra 最短路径交互推演</h1>
    <p>逐帧观察选点、松弛和距离表变化，再修改一条边权重新计算路径。</p>
  </header>
  <DijkstraDemo autoFocusControls />
  <section aria-labelledby="what-you-saw">
    <h2 id="what-you-saw">你刚刚体验了什么</h2>
    <ul>
      <li>教学计划与逐帧讲解同步</li>
      <li>参数变化驱动状态重算</li>
      <li>同一内容可以继续编辑和导出</li>
    </ul>
    <Link to="/app/new?template=dijkstra">基于这个案例创建</Link>
  </section>
</main>
```

- [ ] **Step 4: Register the route**

Add before auth routes:

```tsx
{
  path: "/explore/dijkstra",
  element: <DijkstraExplorePage />,
},
```

- [ ] **Step 5: Run tests**

Run:

```powershell
cd web
npm test -- src/app/router.test.tsx src/features/explore/DijkstraExplorePage.test.tsx
npm run typecheck
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add web/src/features/explore web/src/app/router.tsx web/src/app/router.test.tsx
git commit -m "feat: add public Dijkstra exploration route"
```

---

### Task 9: Verify accessibility, interruption, responsiveness, and production build

**Files:**
- Modify: `web/src/features/demo/DijkstraDemo.test.tsx`
- Modify: `web/src/features/landing/LandingPage.test.tsx`
- Modify: `web/src/test/setup.ts`
- Modify: `web/src/styles/globals.css`
- Create: `docs/qa/eduflow-landing-dijkstra-checklist.md`

**Interfaces:**
- Verifies: reduced motion, visibility pause, keyboard control, theme persistence, mobile stacking, and deterministic fallback

- [ ] **Step 1: Add reduced-motion and visibility tests**

Add:

```tsx
function createReducedMotionMatchMedia(reduce: boolean) {
  return (query: string) =>
    ({
      matches: query === "(prefers-reduced-motion: reduce)" ? reduce : false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList;
}

it("does not autoplay when reduced motion is enabled", async () => {
  window.matchMedia = createReducedMotionMatchMedia(true);
  renderPage(<DijkstraDemo />);
  await userEvent.click(screen.getByRole("button", { name: "观看 60 秒演示" }));
  expect(screen.getByText("准备体验")).toBeVisible();
});

it("pauses when the document becomes hidden", async () => {
  renderPage(<DijkstraDemo />);
  await userEvent.click(screen.getByRole("button", { name: "观看 60 秒演示" }));
  Object.defineProperty(document, "visibilityState", {
    configurable: true,
    value: "hidden",
  });
  document.dispatchEvent(new Event("visibilitychange"));
  expect(screen.getByText("演示已暂停")).toBeVisible();
});
```

Restore `visibilityState` and `matchMedia` in `afterEach`.

- [ ] **Step 2: Add keyboard tests**

Add:

```tsx
it("supports playback keyboard controls without stealing input keys", async () => {
  renderPage(<DijkstraDemo />);
  await userEvent.keyboard(" ");
  expect(screen.getByRole("button", { name: "暂停演示" })).toBeVisible();
  await userEvent.keyboard("{ArrowRight}");
  expect(screen.getByText(/步骤 2/)).toBeVisible();
  await userEvent.keyboard("{ArrowLeft}");
  expect(screen.getByText(/步骤 1/)).toBeVisible();

  const slider = screen.getByRole("slider", { name: "B 到 D 的边权重" });
  slider.focus();
  await userEvent.keyboard("{ArrowRight}");
  expect(slider).toHaveFocus();
  expect(screen.getByText(/步骤 1/)).toBeVisible();
});
```

- [ ] **Step 3: Run all frontend tests**

Run:

```powershell
cd web
npm test
```

Expected: all Vitest suites PASS with no unhandled timer warnings.

- [ ] **Step 4: Run static verification**

Run:

```powershell
cd web
npm run typecheck
npm run lint
npm run build
```

Expected: all commands exit `0`.

- [ ] **Step 5: Perform browser QA**

Start:

```powershell
cd web
npm run dev -- --host 127.0.0.1
```

Check at desktop `1440×900`, tablet `768×1024`, and mobile `390×844`:

- `/` in Light.
- `/` in Dark.
- `/explore/dijkstra` in Light.
- `/explore/dijkstra` in Dark.
- reduced-motion emulation.
- keyboard-only navigation.
- 200% browser zoom.

Record pass/fail for every item in `docs/qa/eduflow-landing-dijkstra-checklist.md`. Every failed item must include the route, viewport, expected result, actual result, and follow-up commit hash.

- [ ] **Step 6: Commit**

```powershell
git add web/src/features/demo/DijkstraDemo.test.tsx web/src/features/landing/LandingPage.test.tsx web/src/test/setup.ts web/src/styles/globals.css docs/qa/eduflow-landing-dijkstra-checklist.md
git commit -m "test: verify landing motion and accessibility"
```

---

## Final Verification

Run:

```powershell
cd web
npm run verify
npm run lint
```

Expected:

- TypeScript exits `0`.
- All Vitest tests pass.
- Vite production build completes.
- Lint exits `0`.
- No public demo request reaches `/api/generate`, `/api/projects`, or the LLM.
- Git status contains no newly modified files outside this plan.

Review the final implementation against:

```text
docs/superpowers/specs/2026-07-24-eduflow-frontend-redesign-design.md
```

Spec coverage for this plan:

- Light/Dark system: Tasks 1–2.
- Smooth motion language: Tasks 1–2, 4–7, 9.
- Stable Dijkstra demo and edge-weight recomputation: Tasks 3–5.
- Hero and complete landing narrative: Tasks 6–7.
- Student and teacher public entry points: Tasks 7–8.
- Performance, accessibility, and reduced-motion fallback: Tasks 2, 4, 9.
- First-phase implementation order: Tasks 1–9.
