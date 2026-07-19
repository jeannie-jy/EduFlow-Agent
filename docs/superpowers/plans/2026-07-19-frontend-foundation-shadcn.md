# EduFlow Shadcn Multi-Theme Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable frontend-only EduFlow foundation in `web/` with a Shadcn Base/Nova application shell, three persistent themes, a responsive canonical teaching workbench, and mock-only interaction states.

**Architecture:** One React component tree serves `dawn`, `deep`, and `canvas` themes through semantic CSS variables on `<html data-theme>`. Shadcn owns every foundational control; theme-aware effects are isolated decorators. This plan does not implement backend integration, RenderScript execution, or teacher-editor domain mutations.

**Tech Stack:** React 18.3.1, TypeScript, Vite, React Router, Shadcn `base-nova` with Base UI, Tailwind CSS, Lucide, Vitest, Testing Library, Playwright, npm

## Global Constraints

- The frontend lives under `web/`; no backend files or API behavior are modified.
- React major version remains 18; Base UI supports React 17, 18 and 19.
- Shadcn is the only foundational component system.
- External effects live in `web/src/components/effects/`, record provenance, and never replace controls.
- Theme ids are exactly `dawn`, `deep`, and `canvas`; persistence key is exactly `eduflow-theme`.
- Theme switching preserves route, editor mock state, playback mock state and form values.
- No screen shows more than two continuously prominent animations.
- Respect `prefers-reduced-motion` and verify 375, 768, 1024 and 1440px widths.
- Use the real EduFlow brand asset derived from the user-provided icon; do not approximate it with CSS, text or inline SVG.
- Every task follows TDD and ends in a focused commit.

---

## File Structure

```text
web/
├── e2e/theme-and-shell.spec.ts
├── public/brand/eduflow-mark.png
├── src/
│   ├── app/App.tsx
│   ├── app/AppProviders.tsx
│   ├── app/router.tsx
│   ├── components/brand/EduFlowBrand.tsx
│   ├── components/effects/PROVENANCE.md
│   ├── components/effects/WorkspaceGrid.tsx
│   ├── components/layout/AppSidebar.tsx
│   ├── components/layout/AppShell.tsx
│   ├── components/layout/ThemeSwitcher.tsx
│   ├── components/workbench/AiStatusStrip.tsx
│   ├── components/workbench/PlanSequence.tsx
│   ├── components/workbench/SimulationPreview.tsx
│   ├── components/workbench/TeachingBrief.tsx
│   ├── components/workbench/WorkbenchPage.tsx
│   ├── pages/RouteEmptyState.tsx
│   ├── theme/ThemeProvider.tsx
│   ├── theme/theme-script.ts
│   ├── theme/theme.test.tsx
│   ├── theme/theme.ts
│   ├── styles/globals.css
│   ├── test/render.tsx
│   └── main.tsx
├── components.json
├── package.json
└── vite.config.ts
```

### Task 1: Scaffold the React and Shadcn foundation

**Files:**
- Create: `web/**` through the Shadcn CLI
- Modify: `web/package.json`
- Create: `web/src/test/setup.ts`
- Create: `web/src/test/smoke.test.tsx`

**Interfaces:**
- Consumes: Node.js `^20.19.0 || >=22.12.0` and npm.
- Produces: a Vite React app, `@/` alias, Shadcn Base/Nova registry configuration and `npm` verification scripts.

- [ ] **Step 1: Create the Shadcn Vite project**

Run from the repository root:

```powershell
npx shadcn@latest create -t vite -p base-nova -n web --no-monorepo --css-variables --pointer
Set-Location web
npm install react@18.3.1 react-dom@18.3.1 react-router-dom
npm install -D @types/react@18 @types/react-dom@18 vitest jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event
```

Expected: `web/components.json` uses Base UI and CSS variables; `npm install` exits 0.

- [ ] **Step 2: Add the test scripts**

Merge these scripts into `web/package.json`:

```json
{
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest",
    "typecheck": "tsc --noEmit",
    "verify": "npm run typecheck && npm run test && npm run build"
  }
}
```

- [ ] **Step 3: Write the smoke test**

Create `web/src/test/smoke.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { App } from "@/app/App";

it("renders the EduFlow application", () => {
  render(<App />);
  expect(screen.getByText("EduFlow")).toBeInTheDocument();
});
```

Create `web/src/test/setup.ts`:

```ts
import "@testing-library/jest-dom/vitest";
```

Configure `vite.config.ts` with `test.environment = "jsdom"`, `test.setupFiles = ["./src/test/setup.ts"]`, and the existing `@` alias.

- [ ] **Step 4: Verify the expected red state**

Run: `npm test`

Expected: FAIL because `src/app/App.tsx` does not yet expose the EduFlow application.

- [ ] **Step 5: Add the minimal application and verify green**

Create `web/src/app/App.tsx`:

```tsx
export function App() {
  return <main><h1>EduFlow</h1></main>;
}
```

Run: `npm test && npm run typecheck && npm run build`

Expected: the smoke test passes, TypeScript exits 0, and the production build succeeds.

- [ ] **Step 6: Commit the scaffold**

```powershell
git add web
git commit -m "chore: scaffold shadcn frontend"
```

### Task 2: Implement persistent three-theme infrastructure

**Files:**
- Create: `web/src/theme/theme.ts`
- Create: `web/src/theme/theme-script.ts`
- Create: `web/src/theme/ThemeProvider.tsx`
- Create: `web/src/theme/theme.test.tsx`
- Modify: `web/index.html`
- Modify: `web/src/styles/globals.css`

**Interfaces:**
- Consumes: `window.matchMedia`, `localStorage`, `document.documentElement.dataset.theme`.
- Produces: `ThemeId`, `THEMES`, `resolveInitialTheme()`, `ThemeProvider`, and `useTheme()`.

- [ ] **Step 1: Write the failing theme tests**

Create `web/src/theme/theme.test.tsx`:

```tsx
import { renderHook, act } from "@testing-library/react";
import { ThemeProvider, useTheme } from "./ThemeProvider";

beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
});

it("defaults a light system to canvas", () => {
  const { result } = renderHook(() => useTheme(), { wrapper: ThemeProvider });
  expect(result.current.theme).toBe("canvas");
});

it("persists a selected theme without replacing children", () => {
  const { result } = renderHook(() => useTheme(), { wrapper: ThemeProvider });
  act(() => result.current.setTheme("dawn"));
  expect(localStorage.getItem("eduflow-theme")).toBe("dawn");
  expect(document.documentElement.dataset.theme).toBe("dawn");
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm test -- src/theme/theme.test.tsx`

Expected: FAIL because `ThemeProvider` does not exist.

- [ ] **Step 3: Add theme types and provider**

Create `web/src/theme/theme.ts`:

```ts
export const THEMES = [
  { id: "dawn", label: "晨光" },
  { id: "deep", label: "深海" },
  { id: "canvas", label: "画布" },
] as const;

export type ThemeId = (typeof THEMES)[number]["id"];
export const THEME_STORAGE_KEY = "eduflow-theme";
export const isThemeId = (value: string | null): value is ThemeId =>
  THEMES.some((theme) => theme.id === value);
```

Create `web/src/theme/ThemeProvider.tsx`:

```tsx
import { createContext, useContext, useEffect, useMemo, useState, type PropsWithChildren } from "react";
import { isThemeId, THEME_STORAGE_KEY, type ThemeId } from "./theme";

type ThemeContextValue = { theme: ThemeId; setTheme: (theme: ThemeId) => void };
const ThemeContext = createContext<ThemeContextValue | null>(null);

function getInitialTheme(): ThemeId {
  const saved = localStorage.getItem(THEME_STORAGE_KEY);
  if (isThemeId(saved)) return saved;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "deep" : "canvas";
}

export function ThemeProvider({ children }: PropsWithChildren) {
  const [theme, setTheme] = useState<ThemeId>(getInitialTheme);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);
  const value = useMemo(() => ({ theme, setTheme }), [theme]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const value = useContext(ThemeContext);
  if (!value) throw new Error("useTheme must be used inside ThemeProvider");
  return value;
}
```

- [ ] **Step 4: Add pre-hydration selection and semantic tokens**

Create `web/src/theme/theme-script.ts`:

```ts
export const themeScript = `(()=>{try{const k="eduflow-theme",v=localStorage.getItem(k),ok=["dawn","deep","canvas"];document.documentElement.dataset.theme=ok.includes(v||"")?v:(matchMedia("(prefers-color-scheme: dark)").matches?"deep":"canvas")}catch{document.documentElement.dataset.theme="canvas"}})();`;
```

Because `index.html` cannot import a TypeScript constant before the app bundle, copy the exact script body between `<script>` tags in the document `<head>` before stylesheet or module loading. Add a unit assertion that the exported constant and the inline body remain byte-identical after whitespace normalization.

Replace Shadcn color variables in `web/src/styles/globals.css` with the three token sets from `design-system/eduflow/MASTER.md`. Include theme transitions and disable them under reduced motion:

```css
html { color-scheme: light; }
html[data-theme="deep"] { color-scheme: dark; }
body { transition: background-color 180ms ease, color 180ms ease; }
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { scroll-behavior: auto !important; animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; transition-duration: 0.01ms !important; }
}
```

- [ ] **Step 5: Run tests and commit**

Run: `npm test -- src/theme/theme.test.tsx && npm run typecheck`

Expected: 2 tests pass and TypeScript exits 0.

```powershell
git add web/index.html web/src/theme web/src/styles/globals.css
git commit -m "feat: add persistent EduFlow themes"
```

### Task 3: Build the branded accessible application shell

**Files:**
- Create: `web/public/brand/eduflow-mark.png`
- Create: `web/src/components/brand/EduFlowBrand.tsx`
- Create: `web/src/components/layout/AppSidebar.tsx`
- Create: `web/src/components/layout/ThemeSwitcher.tsx`
- Create: `web/src/components/layout/AppShell.tsx`
- Create: `web/src/components/layout/AppShell.test.tsx`
- Create: `web/src/app/AppProviders.tsx`

**Interfaces:**
- Consumes: the real EduFlow mark, `useTheme()`, Shadcn Sidebar and Dropdown Menu.
- Produces: `EduFlowBrand`, `AppSidebar`, `ThemeSwitcher`, `AppShell`, and `AppProviders`.

- [ ] **Step 1: Install only the required Shadcn primitives**

Run from `web/`:

```powershell
npx shadcn@latest add sidebar breadcrumb separator dropdown-menu avatar tooltip button badge
```

Inspect every generated file and confirm imports use `@/components/ui`, Base UI primitives and Lucide.

- [ ] **Step 2: Prepare the real brand asset**

Use the supplied EduFlow icon source to create a transparent PNG at exactly `web/public/brand/eduflow-mark.png`. Verify it visually at 32px on `dawn`, `deep`, and `canvas`; do not trace or redraw it.

- [ ] **Step 3: Write the failing shell test**

Create `web/src/components/layout/AppShell.test.tsx`:

```tsx
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/render";
import { AppShell } from "./AppShell";

it("exposes navigation and changes theme", async () => {
  renderWithProviders(<AppShell><main>工作区</main></AppShell>);
  expect(screen.getByRole("navigation", { name: "主导航" })).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: /主题/ }));
  await userEvent.click(screen.getByRole("menuitemradio", { name: "深海" }));
  expect(document.documentElement.dataset.theme).toBe("deep");
});
```

- [ ] **Step 4: Implement the shell**

Compose `SidebarProvider`, a `Sidebar collapsible="icon"`, `SidebarInset`, a sticky header, `Breadcrumb`, `SidebarTrigger`, and `ThemeSwitcher`. Add a visible skip link targeting `#workspace`. `ThemeSwitcher` uses `DropdownMenuRadioGroup` and the three labels from `THEMES`; the trigger accessible name is `主题：{label}`.

Create `web/src/components/brand/EduFlowBrand.tsx`:

```tsx
export function EduFlowBrand({ compact = false }: { compact?: boolean }) {
  return (
    <span className="flex items-center gap-2.5">
      <img src="/brand/eduflow-mark.png" alt="" className="size-8 shrink-0" />
      {!compact && <span className="font-semibold tracking-[-0.02em]">EduFlow</span>}
    </span>
  );
}
```

Use Lucide `LayoutDashboard`, `BookOpen`, `Waypoints`, `Library`, and `Archive` for navigation. Do not include Settings in the first release.

- [ ] **Step 5: Run tests and commit**

Run: `npm test -- src/components/layout/AppShell.test.tsx && npm run typecheck`

Expected: the shell test passes and TypeScript exits 0.

```powershell
git add web/public/brand web/src/components/brand web/src/components/layout web/src/app/AppProviders.tsx web/src/test/render.tsx
git commit -m "feat: add branded shadcn application shell"
```

### Task 4: Build the canonical teaching workbench

**Files:**
- Create: `web/src/components/workbench/TeachingBrief.tsx`
- Create: `web/src/components/workbench/PlanSequence.tsx`
- Create: `web/src/components/workbench/SimulationPreview.tsx`
- Create: `web/src/components/workbench/AiStatusStrip.tsx`
- Create: `web/src/components/workbench/WorkbenchPage.tsx`
- Create: `web/src/components/workbench/WorkbenchPage.test.tsx`

**Interfaces:**
- Consumes: Shadcn form, workflow and data-display primitives plus local mock state.
- Produces: a responsive `WorkbenchPage` demonstrating brief -> plan -> simulation without backend calls.

- [ ] **Step 1: Add the exact Shadcn primitives**

```powershell
npx shadcn@latest add field input-group textarea toggle-group select slider switch collapsible item progress scroll-area tabs table button-group skeleton spinner empty alert
```

- [ ] **Step 2: Write the failing interaction test**

Create `web/src/components/workbench/WorkbenchPage.test.tsx`:

```tsx
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/render";
import { WorkbenchPage } from "./WorkbenchPage";

it("turns a teaching brief into an observable mock plan", async () => {
  renderWithProviders(<WorkbenchPage />);
  const brief = screen.getByRole("textbox", { name: "教学简报" });
  await userEvent.clear(brief);
  await userEvent.type(brief, "用 Dijkstra 演示校园最短路径");
  await userEvent.click(screen.getByRole("button", { name: "生成推演计划" }));
  expect(screen.getByRole("status")).toHaveTextContent("正在生成推演计划");
  expect(screen.getByText("识别知识结构")).toBeVisible();
});
```

- [ ] **Step 3: Implement local mock state and the four regions**

`WorkbenchPage` owns only UI state:

```ts
type GenerationState = "idle" | "planning" | "ready";
const [generation, setGeneration] = useState<GenerationState>("idle");
const [brief, setBrief] = useState("演示 Dijkstra 最短路径算法，并解释每一步如何更新距离表");
```

`TeachingBrief` exposes a labeled `InputGroupTextarea`, stage selector, difficulty `ToggleGroup`, duration `Slider`, and primary Shadcn `Button`. `PlanSequence` renders grouped `Item` rows named “识别知识结构”“设计教学路径”“生成交互演示”“复核讲解与状态”. `SimulationPreview` renders a stable six-node Dijkstra mock, legend, playback buttons, and a semantic HTML distance table. `AiStatusStrip` renders a status message, progress text and recovery action; it never fakes completion through a timer in tests.

Desktop layout:

```tsx
<div className="grid min-h-0 flex-1 grid-cols-1 gap-3 xl:grid-cols-[minmax(18rem,0.8fr)_minmax(20rem,0.9fr)_minmax(32rem,1.55fr)]">
  <TeachingBrief />
  <PlanSequence />
  <SimulationPreview />
</div>
```

At tablet width, brief and plan become a collapsible rail; at mobile width, they stack before preview and secondary settings move to Shadcn Sheet.

- [ ] **Step 4: Verify and commit**

Run: `npm test -- src/components/workbench/WorkbenchPage.test.tsx && npm run typecheck`

Expected: the interaction test passes and no type errors remain.

```powershell
git add web/src/components/workbench web/src/components/ui
git commit -m "feat: add mock-first teaching workbench"
```

### Task 5: Add the audited effect layer

**Files:**
- Create: `web/src/components/effects/PROVENANCE.md`
- Create: `web/src/components/effects/WorkspaceGrid.tsx`
- Create: `web/src/components/effects/GenerationBorder.tsx`
- Create: `web/src/components/effects/effects.test.tsx`
- Modify: `web/src/components/workbench/WorkbenchPage.tsx`
- Modify: `web/src/components/workbench/AiStatusStrip.tsx`

**Interfaces:**
- Consumes: current theme, reduced-motion media query and Shadcn surfaces.
- Produces: decorative `WorkspaceGrid` and `GenerationBorder` wrappers with static fallbacks.

- [ ] **Step 1: Preview before installation**

Run:

```powershell
npx shadcn@latest view '@magicui/animated-grid-pattern'
npx shadcn@latest view '@magicui/border-beam'
```

Reject any generated foundational controls or extra icon libraries. Add only the effect source that passes review:

```powershell
npx shadcn@latest add '@magicui/animated-grid-pattern' '@magicui/border-beam'
```

- [ ] **Step 2: Write the reduced-motion test**

Create `web/src/components/effects/effects.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { WorkspaceGrid } from "./WorkspaceGrid";

it("keeps decorative effects out of the accessibility tree", () => {
  render(<WorkspaceGrid />);
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
  expect(document.querySelector("[aria-hidden='true']")).toBeTruthy();
});
```

- [ ] **Step 3: Wrap and document the upstream effects**

`WorkspaceGrid` selects theme parameters through CSS variables, not conditional business markup. `GenerationBorder` renders only when generation is `planning`. Both wrappers set `aria-hidden="true"`, `pointer-events-none`, and static reduced-motion styles.

Create `PROVENANCE.md` with one table row per effect: local file, upstream component, exact URL, MIT license, installed dependencies and local modifications. Do not add Spotlight, Tracing Beam, Text Generate Effect or Uiverse until a later screen demonstrates a concrete need.

- [ ] **Step 4: Verify the animation budget and commit**

Run: `npm test -- src/components/effects/effects.test.tsx && npm run build`

Expected: effects test passes; build succeeds; the workbench has at most an ambient grid and active generation border as continuous effects.

```powershell
git add web/src/components/effects web/src/components/workbench web/package.json web/package-lock.json
git commit -m "feat: add audited workspace effects"
```

### Task 6: Add routes and honest frontend-only states

**Files:**
- Create: `web/src/app/router.tsx`
- Create: `web/src/pages/RouteEmptyState.tsx`
- Modify: `web/src/app/App.tsx`
- Create: `web/src/app/router.test.tsx`

**Interfaces:**
- Consumes: `AppShell`, `WorkbenchPage`, React Router.
- Produces: seven business routes plus 404, with the workbench at `/` and explicit non-functional states elsewhere.

- [ ] **Step 1: Write route tests**

Create `web/src/app/router.test.tsx` with a memory router and assert these headings:

```ts
const routes = [
  ["/", "教学工作台"],
  ["/new", "新建推演"],
  ["/project/demo/plan", "教学计划确认"],
  ["/project/demo/edit", "教师编辑器"],
  ["/project/demo/play", "交互式播放器"],
  ["/project/demo/export", "导出中心"],
  ["/templates", "知识点模板库"],
  ["/missing", "页面未找到"],
] as const;
```

- [ ] **Step 2: Implement the router**

Nest all routes under `AppShell`. Render `WorkbenchPage` at `/`. Render Shadcn `Empty` through `RouteEmptyState` for unfinished routes with the exact copy “该能力将在对应功能分支中实现；当前页面不连接后端服务。” The 404 action returns to `/`.

- [ ] **Step 3: Verify and commit**

Run: `npm test -- src/app/router.test.tsx && npm run typecheck`

Expected: all 8 route cases pass.

```powershell
git add web/src/app web/src/pages
git commit -m "feat: add frontend-only route states"
```

### Task 7: Add browser, responsive and quality gates

**Files:**
- Create: `web/playwright.config.ts`
- Create: `web/e2e/theme-and-shell.spec.ts`
- Create: `.github/workflows/frontend.yml`
- Modify: `web/package.json`

**Interfaces:**
- Consumes: the complete frontend foundation.
- Produces: repeatable build, unit, theme, route and responsive browser verification.

- [ ] **Step 1: Add Playwright**

Run from `web/`:

```powershell
npm install -D @playwright/test
npx playwright install chromium
```

Add `"test:e2e": "playwright test"` to package scripts. Configure a dev server at `http://127.0.0.1:4173` and Chromium only.

- [ ] **Step 2: Write the browser acceptance test**

Create `web/e2e/theme-and-shell.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

for (const theme of ["晨光", "深海", "画布"] as const) {
  test(`switches and persists ${theme}`, async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /主题/ }).click();
    await page.getByRole("menuitemradio", { name: theme }).click();
    const selected = await page.locator("html").getAttribute("data-theme");
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-theme", selected!);
    await expect(page.getByRole("heading", { name: "教学工作台" })).toBeVisible();
  });
}

for (const width of [375, 768, 1024, 1440]) {
  test(`keeps the workbench reachable at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    await expect(page.getByRole("textbox", { name: "教学简报" })).toBeVisible();
    await expect(page.getByText("Dijkstra 演示预览")).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  });
}
```

- [ ] **Step 3: Add CI**

Create `.github/workflows/frontend.yml` using Node 24 and `npm ci`, then run `npm run typecheck`, `npm test`, `npm run build`, install Chromium with dependencies, and run `npm run test:e2e` for changes under `web/**`.

- [ ] **Step 4: Run the complete gate**

Run from `web/`:

```powershell
npm run typecheck
npm test
npm run build
npm run test:e2e
```

Expected: every command exits 0; three theme persistence cases and four responsive cases pass.

- [ ] **Step 5: Perform visual QA in the user-selected browser**

Capture the same 1440×900 workbench state for `dawn`, `deep`, and `canvas`. Compare each capture with the unified visual target and the original EduFlow posters in one review input. Fix visible spacing, clipping, typography, border, radius and brand-asset mismatches, then repeat the comparison. Do not use Playwright for manual visual inspection unless the user explicitly selects it.

- [ ] **Step 6: Commit the quality gate**

```powershell
git add web .github/workflows/frontend.yml
git commit -m "test: verify themes and responsive shell"
```

## Self-Review

- Spec coverage: themes, Shadcn-only foundation, real brand asset, canonical workbench, reduced motion, responsive widths, route states and visual QA each map to a task.
- Scope boundary: backend, RenderScript execution and teacher-editor mutations are excluded and receive separate feature plans.
- Effect budget: this plan installs two effects only; later candidates require screen-specific justification.
- Type consistency: theme ids, persistence key, provider API and generation states are defined once and reused consistently.
- Instruction scan: every implementation action includes exact code, a registry command or a named visual-review procedure.

## Execution Handoff

Execute with `superpowers:subagent-driven-development`: one fresh worker per task, specification review first, code-quality review second, then continue to the next task. The user has already selected this execution mode; begin only after the present design-document review is accepted.
