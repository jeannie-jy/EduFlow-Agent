# Frontend Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status:** Superseded by the approved shadcn and motion-governance amendment. Do not execute this revision. Replace it after the project poster has been mapped into the design system.

**Goal:** 在 `web/` 中建立可运行、可测试的 React 前端基础工程，交付 7 条业务路由、404 页面、应用外壳、Query Provider 和完整质量门禁。

**Architecture:** 本计划只实现 Mock-First MVP 系列中的 foundation 子系统。应用采用 React 18 CSR，路由定义与页面组件分离，根级 Provider 只负责跨页面基础设施；业务数据契约、MSW、播放器和教师编辑器分别在后续独立计划中实现。

**Tech Stack:** React 18.3.1、TypeScript 6.0.3、Vite 8.1.5、React Router 7.18.1、TanStack Query 5.101.2、Vitest 4.1.10、Testing Library、Playwright 1.61.1、ESLint 10.7.0、Prettier 3.9.5、npm

## Global Constraints

- Node.js 版本必须满足 `^20.19.0 || >=22.12.0`；项目 README 的最低要求仍表述为 Node.js 20+。
- React 主版本固定为 18。
- 前端工程必须位于仓库根目录下的 `web/`。
- 路由固定为 7 条业务路由加 1 个 404 页面；系统设置不进入首期范围。
- 本分支不实现 API Client、MSW、RenderScript、播放器或教师编辑器业务逻辑。
- 所有页面必须具有可识别的标题、用途说明和明确空状态。
- 每个任务完成后运行其指定测试并单独提交。

---

## Plan Series Boundary

已确认的前端设计拆分为以下独立实施计划：

1. `frontend-foundation`：本计划，建立工程、路由、外壳和质量门禁。
2. `frontend-contract-mocks`：领域契约、适配器、Repository、MSW 与生成进度模拟。
3. `frontend-create-flow`：工作台、新建推演和教学计划确认链路。
4. `frontend-renderer-core`：RenderScript 解释器、首批对象、动画和播放器状态机。
5. `frontend-teacher-editor`：帧管理、属性草稿、锁定和局部重生成。
6. `frontend-advanced-delivery`：高级渲染器、导出、反馈、版本和 UI 打磨。

每份计划以前一分支合并至 `develop` 为起点。本计划完成时只要求基础页面可导航，不用模拟业务数据。

## File Structure

```text
web/
├── e2e/
│   └── routes.spec.ts
├── src/
│   ├── app/
│   │   ├── App.test.tsx
│   │   ├── App.tsx
│   │   ├── AppProviders.test.tsx
│   │   ├── AppProviders.tsx
│   │   ├── queryClient.ts
│   │   ├── router.test.tsx
│   │   └── router.tsx
│   ├── components/
│   │   ├── layout/
│   │   │   ├── AppShell.css
│   │   │   ├── AppShell.test.tsx
│   │   │   └── AppShell.tsx
│   │   └── ui/
│   │       ├── PagePlaceholder.css
│   │       └── PagePlaceholder.tsx
│   ├── pages/
│   │   ├── DashboardPage.tsx
│   │   ├── EditorPage.tsx
│   │   ├── ExportPage.tsx
│   │   ├── NewProjectPage.tsx
│   │   ├── NotFoundPage.tsx
│   │   ├── PlanPage.tsx
│   │   ├── PlayerPage.tsx
│   │   └── TemplatesPage.tsx
│   ├── styles/
│   │   ├── global.css
│   │   └── tokens.css
│   ├── test/
│   │   ├── render.tsx
│   │   └── setup.ts
│   └── main.tsx
├── .prettierignore
├── .prettierrc.json
├── eslint.config.js
├── index.html
├── package.json
├── package-lock.json
├── playwright.config.ts
├── tsconfig.app.json
├── tsconfig.json
├── tsconfig.node.json
└── vite.config.ts

.github/workflows/frontend.yml
.gitignore
```

---

### Task 1: Bootstrap the React and test toolchain

**Files:**

- Create: `web/package.json`
- Create: `web/tsconfig.json`
- Create: `web/tsconfig.app.json`
- Create: `web/tsconfig.node.json`
- Create: `web/vite.config.ts`
- Create: `web/eslint.config.js`
- Create: `web/.prettierrc.json`
- Create: `web/.prettierignore`
- Create: `web/index.html`
- Create: `web/src/test/setup.ts`
- Create: `web/src/app/App.test.tsx`
- Create: `web/src/app/App.tsx`
- Create: `web/src/main.tsx`
- Modify: `.gitignore`
- Generate: `web/package-lock.json`

**Interfaces:**

- Consumes: Node.js `^20.19.0 || >=22.12.0` and npm.
- Produces: `App(): JSX.Element`, Vite build entry, Vitest/jsdom environment, lint/format/typecheck/build scripts.

- [ ] **Step 1: Create the package manifest**

Create `web/package.json`:

```json
{
  "name": "eduflow-web",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "engines": {
    "node": "^20.19.0 || >=22.12.0"
  },
  "scripts": {
    "dev": "vite",
    "build": "npm run typecheck && vite build",
    "lint": "eslint .",
    "format": "prettier --write .",
    "format:check": "prettier --check .",
    "typecheck": "tsc --noEmit -p tsconfig.app.json --pretty false && tsc --noEmit -p tsconfig.node.json --pretty false",
    "test": "vitest run",
    "test:watch": "vitest",
    "test:e2e": "playwright test"
  },
  "dependencies": {
    "@tanstack/react-query": "5.101.2",
    "react": "18.3.1",
    "react-dom": "18.3.1",
    "react-router-dom": "7.18.1"
  },
  "devDependencies": {
    "@eslint/js": "10.0.1",
    "@playwright/test": "1.61.1",
    "@testing-library/jest-dom": "6.9.1",
    "@testing-library/react": "16.3.2",
    "@testing-library/user-event": "14.6.1",
    "@types/node": "24.13.3",
    "@types/react": "18.3.31",
    "@types/react-dom": "18.3.7",
    "@vitejs/plugin-react": "6.0.3",
    "eslint": "10.7.0",
    "eslint-plugin-react-hooks": "7.1.1",
    "eslint-plugin-react-refresh": "0.5.3",
    "globals": "17.7.0",
    "jsdom": "29.1.1",
    "prettier": "3.9.5",
    "typescript": "6.0.3",
    "typescript-eslint": "8.64.0",
    "vite": "8.1.5",
    "vitest": "4.1.10"
  }
}
```

- [ ] **Step 2: Create TypeScript, Vite, ESLint, and Prettier configuration**

Create `web/tsconfig.json`:

```json
{
  "files": [],
  "references": [{ "path": "./tsconfig.app.json" }, { "path": "./tsconfig.node.json" }]
}
```

Create `web/tsconfig.app.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "allowJs": false,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src"]
}
```

Create `web/tsconfig.node.json`:

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "allowImportingTsExtensions": true,
    "strict": true,
    "noEmit": true,
    "types": ["node"]
  },
  "include": ["vite.config.ts", "playwright.config.ts", "eslint.config.js"]
}
```

Create `web/vite.config.ts`:

```ts
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    css: true,
  },
});
```

Create `web/eslint.config.js`:

```js
import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "coverage", "playwright-report", "test-results"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      globals: { ...globals.browser, ...globals.es2022 },
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.flat.recommended.rules,
      ...reactRefresh.configs.vite.rules,
    },
  },
);
```

Create `web/.prettierrc.json`:

```json
{
  "semi": true,
  "singleQuote": false,
  "trailingComma": "all",
  "printWidth": 100
}
```

Create `web/.prettierignore`:

```text
dist
coverage
playwright-report
test-results
```

- [ ] **Step 3: Create the HTML entry and test setup**

Create `web/index.html`:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="description" content="EduFlow-Agent 交互式教学推演" />
    <title>EduFlow-Agent</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

Create `web/src/test/setup.ts`:

```ts
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 4: Write the failing application smoke test**

Create `web/src/app/App.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { App } from "./App";

describe("App", () => {
  it("renders the product name", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: "EduFlow-Agent" })).toBeInTheDocument();
  });
});
```

- [ ] **Step 5: Install dependencies and verify the test fails**

Run:

```powershell
Set-Location web
npm install
npm test -- --run src/app/App.test.tsx
```

Expected: FAIL because `src/app/App.tsx` does not exist.

- [ ] **Step 6: Implement the minimal application**

Create `web/src/app/App.tsx`:

```tsx
export function App() {
  return (
    <main>
      <h1>EduFlow-Agent</h1>
    </main>
  );
}
```

Create `web/src/main.tsx`:

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./app/App";

const root = document.getElementById("root");

if (!root) {
  throw new Error("Root element #root was not found");
}

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

Append to the repository root `.gitignore`:

```gitignore
# Frontend test artifacts
/web/coverage/
/web/playwright-report/
/web/test-results/
```

- [ ] **Step 7: Run the foundation quality checks**

Run:

```powershell
Set-Location web
npm test -- --run src/app/App.test.tsx
npm run typecheck
npm run lint
npm run build
```

Expected: one test passes; typecheck and lint exit 0; Vite produces `web/dist/index.html`.

- [ ] **Step 8: Commit the toolchain**

```powershell
git add .gitignore web
git commit -m "chore: bootstrap frontend toolchain"
```

---

### Task 2: Add the route map and placeholder pages

**Files:**

- Create: `web/src/app/router.test.tsx`
- Create: `web/src/app/router.tsx`
- Create: `web/src/components/ui/PagePlaceholder.tsx`
- Create: `web/src/pages/DashboardPage.tsx`
- Create: `web/src/pages/NewProjectPage.tsx`
- Create: `web/src/pages/PlanPage.tsx`
- Create: `web/src/pages/EditorPage.tsx`
- Create: `web/src/pages/PlayerPage.tsx`
- Create: `web/src/pages/ExportPage.tsx`
- Create: `web/src/pages/TemplatesPage.tsx`
- Create: `web/src/pages/NotFoundPage.tsx`
- Modify: `web/src/app/App.tsx`

**Interfaces:**

- Consumes: React Router `RouteObject`, URL parameters `:id`.
- Produces: exported `routeObjects`, browser `router`, and 8 routable page components with stable accessible headings.

- [ ] **Step 1: Write the failing route contract test**

Create `web/src/app/router.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { routeObjects } from "./router";

const cases = [
  ["/", "工作台"],
  ["/new", "新建推演"],
  ["/project/demo/plan", "教学计划确认"],
  ["/project/demo/edit", "教师编辑器"],
  ["/project/demo/play", "交互式播放器"],
  ["/project/demo/export", "导出中心"],
  ["/templates", "知识点模板库"],
  ["/missing", "页面未找到"],
] as const;

describe("route map", () => {
  it.each(cases)("renders %s", async (path, heading) => {
    const router = createMemoryRouter(routeObjects, { initialEntries: [path] });
    render(<RouterProvider router={router} />);
    expect(await screen.findByRole("heading", { name: heading })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the route test to verify it fails**

Run:

```powershell
Set-Location web
npm test -- --run src/app/router.test.tsx
```

Expected: FAIL because `src/app/router.tsx` does not exist.

- [ ] **Step 3: Implement the shared placeholder and pages**

Create `web/src/components/ui/PagePlaceholder.tsx`:

```tsx
type PagePlaceholderProps = {
  title: string;
  description: string;
};

export function PagePlaceholder({ title, description }: PagePlaceholderProps) {
  return (
    <section aria-labelledby="page-title">
      <p>EduFlow-Agent</p>
      <h1 id="page-title">{title}</h1>
      <p>{description}</p>
      <div role="status">该模块的业务能力将在对应功能分支中实现。</div>
    </section>
  );
}
```

Create the page modules:

```tsx
// web/src/pages/DashboardPage.tsx
import { PagePlaceholder } from "../components/ui/PagePlaceholder";
export function DashboardPage() {
  return <PagePlaceholder title="工作台" description="查看最近项目并开始新的教学推演。" />;
}

// web/src/pages/NewProjectPage.tsx
import { PagePlaceholder } from "../components/ui/PagePlaceholder";
export function NewProjectPage() {
  return <PagePlaceholder title="新建推演" description="输入知识点、材料或模板来创建推演。" />;
}

// web/src/pages/PlanPage.tsx
import { PagePlaceholder } from "../components/ui/PagePlaceholder";
export function PlanPage() {
  return <PagePlaceholder title="教学计划确认" description="检查教学目标、大纲和生成风险。" />;
}

// web/src/pages/EditorPage.tsx
import { PagePlaceholder } from "../components/ui/PagePlaceholder";
export function EditorPage() {
  return <PagePlaceholder title="教师编辑器" description="逐帧编辑、锁定和重新生成教学内容。" />;
}

// web/src/pages/PlayerPage.tsx
import { PagePlaceholder } from "../components/ui/PagePlaceholder";
export function PlayerPage() {
  return <PagePlaceholder title="交互式播放器" description="逐帧播放并调整教学参数。" />;
}

// web/src/pages/ExportPage.tsx
import { PagePlaceholder } from "../components/ui/PagePlaceholder";
export function ExportPage() {
  return <PagePlaceholder title="导出中心" description="配置并跟踪教学视频导出任务。" />;
}

// web/src/pages/TemplatesPage.tsx
import { PagePlaceholder } from "../components/ui/PagePlaceholder";
export function TemplatesPage() {
  return <PagePlaceholder title="知识点模板库" description="浏览可复用的计算机科学知识点模板。" />;
}

// web/src/pages/NotFoundPage.tsx
import { Link } from "react-router-dom";
export function NotFoundPage() {
  return (
    <main>
      <h1>页面未找到</h1>
      <p>请求的页面不存在或已被移动。</p>
      <Link to="/">返回工作台</Link>
    </main>
  );
}
```

- [ ] **Step 4: Implement the router and connect App**

Create `web/src/app/router.tsx`:

```tsx
import { createBrowserRouter, type RouteObject } from "react-router-dom";
import { DashboardPage } from "../pages/DashboardPage";
import { EditorPage } from "../pages/EditorPage";
import { ExportPage } from "../pages/ExportPage";
import { NewProjectPage } from "../pages/NewProjectPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { PlanPage } from "../pages/PlanPage";
import { PlayerPage } from "../pages/PlayerPage";
import { TemplatesPage } from "../pages/TemplatesPage";

export const routeObjects: RouteObject[] = [
  { path: "/", element: <DashboardPage /> },
  { path: "/new", element: <NewProjectPage /> },
  { path: "/project/:id/plan", element: <PlanPage /> },
  { path: "/project/:id/edit", element: <EditorPage /> },
  { path: "/project/:id/play", element: <PlayerPage /> },
  { path: "/project/:id/export", element: <ExportPage /> },
  { path: "/templates", element: <TemplatesPage /> },
  { path: "*", element: <NotFoundPage /> },
];

export const router = createBrowserRouter(routeObjects);
```

Replace `web/src/app/App.tsx` with:

```tsx
import { RouterProvider } from "react-router-dom";
import { router } from "./router";

export function App() {
  return <RouterProvider router={router} />;
}
```

Update `web/src/app/App.test.tsx` to avoid binding the test to the browser router:

```tsx
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { routeObjects } from "./router";

describe("App", () => {
  it("renders the dashboard at the root route", async () => {
    const router = createMemoryRouter(routeObjects, { initialEntries: ["/"] });
    render(<RouterProvider router={router} />);
    expect(await screen.findByRole("heading", { name: "工作台" })).toBeInTheDocument();
  });
});
```

- [ ] **Step 5: Run route and regression tests**

Run:

```powershell
Set-Location web
npm test -- --run src/app/App.test.tsx src/app/router.test.tsx
npm run typecheck
```

Expected: 9 tests pass and TypeScript exits 0.

- [ ] **Step 6: Commit the routes**

```powershell
git add web/src
git commit -m "feat: add frontend route placeholders"
```

---

### Task 3: Add root providers and reusable test rendering

**Files:**

- Create: `web/src/app/queryClient.ts`
- Create: `web/src/app/AppProviders.tsx`
- Create: `web/src/app/AppProviders.test.tsx`
- Create: `web/src/test/render.tsx`
- Modify: `web/src/main.tsx`

**Interfaces:**

- Consumes: React children and optional `QueryClient`.
- Produces: `createAppQueryClient(): QueryClient`, `AppProviders`, and `renderWithProviders(ui, options)` for later features.

- [ ] **Step 1: Write the failing provider test**

Create `web/src/app/AppProviders.test.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../test/render";

function QueryProbe() {
  const query = useQuery({
    queryKey: ["foundation-probe"],
    queryFn: async () => "ready",
  });

  return <p>{query.data ?? "loading"}</p>;
}

describe("AppProviders", () => {
  it("provides a QueryClient", async () => {
    renderWithProviders(<QueryProbe />);
    expect(await screen.findByText("ready")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the provider test to verify it fails**

Run:

```powershell
Set-Location web
npm test -- --run src/app/AppProviders.test.tsx
```

Expected: FAIL because `src/test/render.tsx` does not exist.

- [ ] **Step 3: Implement QueryClient and providers**

Create `web/src/app/queryClient.ts`:

```ts
import { QueryClient } from "@tanstack/react-query";

export function createAppQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: 1,
        staleTime: 30_000,
      },
      mutations: {
        retry: 0,
      },
    },
  });
}
```

Create `web/src/app/AppProviders.tsx`:

```tsx
import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { type PropsWithChildren, useState } from "react";
import { createAppQueryClient } from "./queryClient";

type AppProvidersProps = PropsWithChildren<{
  queryClient?: QueryClient;
}>;

export function AppProviders({ children, queryClient }: AppProvidersProps) {
  const [client] = useState(() => queryClient ?? createAppQueryClient());
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
```

Create `web/src/test/render.tsx`:

```tsx
import { QueryClient } from "@tanstack/react-query";
import { render, type RenderOptions } from "@testing-library/react";
import { type ReactElement, type ReactNode } from "react";
import { AppProviders } from "../app/AppProviders";

export function renderWithProviders(ui: ReactElement, options?: RenderOptions) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  function Wrapper({ children }: { children: ReactNode }) {
    return <AppProviders queryClient={queryClient}>{children}</AppProviders>;
  }

  return { queryClient, ...render(ui, { wrapper: Wrapper, ...options }) };
}
```

Wrap the application in `web/src/main.tsx`:

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./app/App";
import { AppProviders } from "./app/AppProviders";

const root = document.getElementById("root");

if (!root) {
  throw new Error("Root element #root was not found");
}

createRoot(root).render(
  <StrictMode>
    <AppProviders>
      <App />
    </AppProviders>
  </StrictMode>,
);
```

- [ ] **Step 4: Run provider and full unit tests**

Run:

```powershell
Set-Location web
npm test
npm run typecheck
```

Expected: all tests pass; no open handles or TypeScript errors.

- [ ] **Step 5: Commit the providers**

```powershell
git add web/src/app web/src/test web/src/main.tsx
git commit -m "feat: add frontend application providers"
```

---

### Task 4: Build the accessible application shell

**Files:**

- Create: `web/src/components/layout/AppShell.test.tsx`
- Create: `web/src/components/layout/AppShell.tsx`
- Create: `web/src/components/layout/AppShell.css`
- Create: `web/src/components/ui/PagePlaceholder.css`
- Create: `web/src/styles/tokens.css`
- Create: `web/src/styles/global.css`
- Modify: `web/src/components/ui/PagePlaceholder.tsx`
- Modify: `web/src/app/router.tsx`
- Modify: `web/src/main.tsx`

**Interfaces:**

- Consumes: React Router location and nested route outlet.
- Produces: keyboard-accessible global navigation, responsive content shell, design tokens, and consistent empty-state page surface.

- [ ] **Step 1: Write the failing shell navigation test**

Create `web/src/components/layout/AppShell.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { routeObjects } from "../../app/router";

describe("AppShell", () => {
  it("exposes primary navigation and the current page", async () => {
    const router = createMemoryRouter(routeObjects, { initialEntries: ["/templates"] });
    render(<RouterProvider router={router} />);

    expect(screen.getByRole("navigation", { name: "主导航" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "模板库" })).toHaveAttribute("aria-current", "page");
    expect(await screen.findByRole("heading", { name: "知识点模板库" })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the shell test to verify it fails**

Run:

```powershell
Set-Location web
npm test -- --run src/components/layout/AppShell.test.tsx
```

Expected: FAIL because no `主导航` landmark exists.

- [ ] **Step 3: Implement the application shell**

Create `web/src/components/layout/AppShell.tsx`:

```tsx
import { NavLink, Outlet } from "react-router-dom";
import "./AppShell.css";

const navItems = [
  { to: "/", label: "工作台", end: true },
  { to: "/new", label: "新建推演", end: false },
  { to: "/templates", label: "模板库", end: false },
] as const;

export function AppShell() {
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        跳到主要内容
      </a>
      <header className="app-header">
        <NavLink className="brand" to="/" aria-label="EduFlow-Agent 工作台">
          <span className="brand-mark" aria-hidden="true">E</span>
          <span>EduFlow-Agent</span>
        </NavLink>
        <nav aria-label="主导航">
          <ul className="nav-list">
            {navItems.map((item) => (
              <li key={item.to}>
                <NavLink
                  className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}
                  end={item.end}
                  to={item.to}
                >
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </header>
      <main className="app-content" id="main-content">
        <Outlet />
      </main>
    </div>
  );
}
```

Create `web/src/components/layout/AppShell.css`:

```css
.app-shell {
  min-height: 100vh;
}

.skip-link {
  position: fixed;
  left: 1rem;
  top: 1rem;
  z-index: 10;
  padding: 0.75rem 1rem;
  border-radius: var(--radius-sm);
  background: var(--color-text);
  color: var(--color-surface);
  transform: translateY(-200%);
}

.skip-link:focus {
  transform: translateY(0);
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 4.5rem;
  padding: 0 2rem;
  border-bottom: 1px solid var(--color-border);
  background: color-mix(in srgb, var(--color-surface) 92%, transparent);
}

.brand,
.nav-link {
  color: inherit;
  text-decoration: none;
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 0.75rem;
  font-weight: 750;
}

.brand-mark {
  display: grid;
  width: 2rem;
  height: 2rem;
  place-items: center;
  border-radius: 0.65rem;
  background: var(--color-accent);
  color: white;
}

.nav-list {
  display: flex;
  gap: 0.5rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

.nav-link {
  display: inline-flex;
  padding: 0.65rem 0.9rem;
  border-radius: var(--radius-sm);
  color: var(--color-muted);
}

.nav-link:hover,
.nav-link.active {
  background: var(--color-accent-soft);
  color: var(--color-accent-strong);
}

.app-content {
  width: min(100% - 2rem, 80rem);
  margin: 0 auto;
  padding: 4rem 0;
}

@media (max-width: 42rem) {
  .app-header {
    align-items: flex-start;
    flex-direction: column;
    gap: 1rem;
    padding: 1rem;
  }

  .nav-list {
    flex-wrap: wrap;
  }

  .app-content {
    padding-top: 2rem;
  }
}
```

- [ ] **Step 4: Add design tokens and global styles**

Create `web/src/styles/tokens.css`:

```css
:root {
  --color-canvas: #f4f6fb;
  --color-surface: #ffffff;
  --color-text: #172033;
  --color-muted: #657086;
  --color-border: #dce2ec;
  --color-accent: #4f46e5;
  --color-accent-strong: #3730a3;
  --color-accent-soft: #eeecff;
  --shadow-card: 0 1.25rem 3rem rgb(39 51 89 / 10%);
  --radius-sm: 0.75rem;
  --radius-lg: 1.5rem;
  font-family: Inter, "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
  color: var(--color-text);
  background: var(--color-canvas);
  font-synthesis: none;
  text-rendering: optimizeLegibility;
}
```

Create `web/src/styles/global.css`:

```css
@import "./tokens.css";

* {
  box-sizing: border-box;
}

html {
  min-width: 320px;
  background: var(--color-canvas);
}

body {
  min-width: 320px;
  min-height: 100vh;
  margin: 0;
}

button,
input,
textarea,
select {
  font: inherit;
}

:focus-visible {
  outline: 3px solid color-mix(in srgb, var(--color-accent) 45%, transparent);
  outline-offset: 3px;
}
```

Create `web/src/components/ui/PagePlaceholder.css`:

```css
.page-placeholder {
  max-width: 52rem;
  padding: clamp(2rem, 6vw, 4.5rem);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
  box-shadow: var(--shadow-card);
}

.page-eyebrow {
  margin: 0 0 0.75rem;
  color: var(--color-accent-strong);
  font-size: 0.78rem;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.page-placeholder h1 {
  margin: 0;
  font-size: clamp(2rem, 5vw, 3.75rem);
  line-height: 1.05;
}

.page-description {
  max-width: 42rem;
  margin: 1.25rem 0 2.5rem;
  color: var(--color-muted);
  font-size: 1.1rem;
  line-height: 1.75;
}

.empty-state {
  padding: 1rem 1.25rem;
  border-radius: var(--radius-sm);
  background: var(--color-accent-soft);
  color: var(--color-accent-strong);
}
```

Replace `web/src/components/ui/PagePlaceholder.tsx` with:

```tsx
import "./PagePlaceholder.css";

type PagePlaceholderProps = {
  title: string;
  description: string;
};

export function PagePlaceholder({ title, description }: PagePlaceholderProps) {
  return (
    <section className="page-placeholder" aria-labelledby="page-title">
      <p className="page-eyebrow">EduFlow-Agent</p>
      <h1 id="page-title">{title}</h1>
      <p className="page-description">{description}</p>
      <div className="empty-state" role="status">
        该模块的业务能力将在对应功能分支中实现。
      </div>
    </section>
  );
}
```

- [ ] **Step 5: Nest routes under the shell and load global CSS**

Replace `web/src/app/router.tsx` route composition while keeping existing imports for pages:

```tsx
import { createBrowserRouter, type RouteObject } from "react-router-dom";
import { AppShell } from "../components/layout/AppShell";
import { DashboardPage } from "../pages/DashboardPage";
import { EditorPage } from "../pages/EditorPage";
import { ExportPage } from "../pages/ExportPage";
import { NewProjectPage } from "../pages/NewProjectPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { PlanPage } from "../pages/PlanPage";
import { PlayerPage } from "../pages/PlayerPage";
import { TemplatesPage } from "../pages/TemplatesPage";

export const routeObjects: RouteObject[] = [
  {
    element: <AppShell />,
    children: [
      { path: "/", element: <DashboardPage /> },
      { path: "/new", element: <NewProjectPage /> },
      { path: "/project/:id/plan", element: <PlanPage /> },
      { path: "/project/:id/edit", element: <EditorPage /> },
      { path: "/project/:id/play", element: <PlayerPage /> },
      { path: "/project/:id/export", element: <ExportPage /> },
      { path: "/templates", element: <TemplatesPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];

export const router = createBrowserRouter(routeObjects);
```

Add this as the first application import in `web/src/main.tsx`:

```tsx
import "./styles/global.css";
```

- [ ] **Step 6: Run accessibility-oriented component tests and quality checks**

Run:

```powershell
Set-Location web
npm test
npm run typecheck
npm run lint
npm run format:check
npm run build
```

Expected: all tests pass; every command exits 0; the production build succeeds.

- [ ] **Step 7: Commit the application shell**

```powershell
git add web/src
git commit -m "feat: add accessible frontend shell"
```

---

### Task 5: Add browser smoke tests and frontend CI

**Files:**

- Create: `web/playwright.config.ts`
- Create: `web/e2e/routes.spec.ts`
- Create: `.github/workflows/frontend.yml`

**Interfaces:**

- Consumes: `npm run dev`, all stable route headings, committed `web/package-lock.json`.
- Produces: local Chromium smoke suite and GitHub Actions quality gate for changes under `web/`.

- [ ] **Step 1: Create Playwright configuration**

Create `web/playwright.config.ts`:

```ts
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: "html",
  use: {
    baseURL: "http://127.0.0.1:4173",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: {
    command: "npm run dev -- --host 127.0.0.1 --port 4173",
    url: "http://127.0.0.1:4173",
    reuseExistingServer: !process.env.CI,
  },
});
```

- [ ] **Step 2: Write browser route and responsive smoke tests**

Create `web/e2e/routes.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

const routes = [
  ["/", "工作台"],
  ["/new", "新建推演"],
  ["/project/demo/plan", "教学计划确认"],
  ["/project/demo/edit", "教师编辑器"],
  ["/project/demo/play", "交互式播放器"],
  ["/project/demo/export", "导出中心"],
  ["/templates", "知识点模板库"],
  ["/missing", "页面未找到"],
] as const;

for (const [path, heading] of routes) {
  test(`${path} renders ${heading}`, async ({ page }) => {
    await page.goto(path);
    await expect(page.getByRole("heading", { name: heading })).toBeVisible();
  });
}

test("mobile layout keeps navigation and content accessible", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.getByRole("navigation", { name: "主导航" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "工作台" })).toBeVisible();
});
```

- [ ] **Step 3: Install the Chromium runtime and run the browser suite**

Run:

```powershell
Set-Location web
npx playwright install chromium
npm run test:e2e
```

Expected: 9 Chromium tests pass.

- [ ] **Step 4: Add the frontend CI workflow**

Create `.github/workflows/frontend.yml`:

```yaml
name: Frontend

on:
  pull_request:
    paths:
      - "web/**"
      - ".github/workflows/frontend.yml"
  push:
    branches: [main, develop]
    paths:
      - "web/**"
      - ".github/workflows/frontend.yml"

jobs:
  verify:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: web
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 24
          cache: npm
          cache-dependency-path: web/package-lock.json
      - run: npm ci
      - run: npm run format:check
      - run: npm run lint
      - run: npm run typecheck
      - run: npm test
      - run: npm run build
      - run: npx playwright install --with-deps chromium
      - run: npm run test:e2e
```

- [ ] **Step 5: Run the complete local verification gate**

Run from `web/`:

```powershell
npm run format:check
npm run lint
npm run typecheck
npm test
npm run build
npm run test:e2e
```

Expected: formatting, lint, typecheck, unit tests, production build, and 9 browser tests all pass.

- [ ] **Step 6: Commit CI and browser tests**

```powershell
git add web/playwright.config.ts web/e2e .github/workflows/frontend.yml
git commit -m "test: add frontend browser and CI checks"
```

---

## Final Branch Verification

Run from repository root:

```powershell
git status --short
Set-Location web
npm run format:check
npm run lint
npm run typecheck
npm test
npm run build
npm run test:e2e
```

Expected:

- `git status --short` is empty before verification begins and remains empty afterward except ignored build/test artifacts.
- All 11 unit/component tests pass: 1 App test, 8 route cases, 1 Provider test, and 1 AppShell test.
- All 9 Playwright tests pass.
- `web/dist/index.html` is generated.
- The branch contains five focused implementation commits plus the design and plan documentation commits, with no frontend business implementation beyond the foundation scope.
