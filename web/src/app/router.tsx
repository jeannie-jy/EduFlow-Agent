import { createBrowserRouter, Outlet, type RouteObject } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { WorkbenchPage } from "@/components/workbench/WorkbenchPage";

// 公开页面
import { LandingPage } from "@/features/landing/LandingPage";
import { LoginPage } from "@/features/auth/LoginPage";
import { RegisterPage } from "@/features/auth/RegisterPage";

// 应用页面
import { Dashboard } from "@/pages/Dashboard";
import { NewProject } from "@/pages/NewProject";
import { PlanConfirm } from "@/pages/PlanConfirm";
import { Editor } from "@/pages/Editor";
import { Player } from "@/pages/Player";
import { ExportCenter } from "@/pages/ExportCenter";
import { TemplateBrowser } from "@/pages/TemplateBrowser";
import { VersionHistory } from "@/pages/VersionHistory";
import { NotFound } from "@/pages/NotFound";

// ── 布局 ────────────────────────────────────────────────────

function AppLayout() {
  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}

// ── 路由 ────────────────────────────────────────────────────

export const appRoutes: RouteObject[] = [
  // 公开路由（无 AppShell）
  {
    path: "/",
    element: <LandingPage />,
  },
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    path: "/register",
    element: <RegisterPage />,
  },

  // 应用路由（包裹 AppShell）
  {
    path: "/app",
    element: <AppLayout />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: "new", element: <NewProject /> },
      {
        path: "project/:projectId/plan",
        element: <PlanConfirm />,
      },
      {
        path: "project/:projectId/edit",
        element: <Editor />,
      },
      {
        path: "project/:projectId/play",
        element: <Player />,
      },
      {
        path: "project/:projectId/export",
        element: <ExportCenter />,
      },
      {
        path: "project/:projectId/versions",
        element: <VersionHistory />,
      },
      { path: "templates", element: <TemplateBrowser /> },
    ],
  },

  // 兜底
  {
    path: "*",
    element: <NotFound />,
  },
];

export const appRouter = createBrowserRouter(appRoutes);

// 保留旧工作台作为默认路由（/app 首页）
export { WorkbenchPage };