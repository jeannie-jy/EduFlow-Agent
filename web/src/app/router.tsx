import { createBrowserRouter, Navigate, Outlet, useParams, type RouteObject } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";

// 公开页面
import { LandingPage } from "@/features/landing/LandingPage";
import { LoginPage } from "@/features/auth/LoginPage";
import { RegisterPage } from "@/features/auth/RegisterPage";

// 应用页面
import { Dashboard } from "@/pages/Dashboard";
import { NewProject } from "@/pages/NewProject";
import { ProjectWorkspace } from "@/pages/ProjectWorkspace";
import { TemplateBrowser } from "@/pages/TemplateBrowser";
import { NotFound } from "@/pages/NotFound";

// ── 旧路由重定向 ────────────────────────────────────────────

function RedirectToTab({ tab }: { tab: string }) {
  const { projectId } = useParams();
  return <Navigate to={`/app/project/${projectId}?tab=${tab}`} replace />;
}

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
      { path: "templates", element: <TemplateBrowser /> },

      // 统一项目工作区
      { path: "project/:projectId", element: <ProjectWorkspace /> },

      // 旧路由 → 重定向到工作区
      {
        path: "project/:projectId/play",
        element: <RedirectToTab tab="play" />,
      },
      {
        path: "project/:projectId/edit",
        element: <RedirectToTab tab="edit" />,
      },
      {
        path: "project/:projectId/plan",
        element: <RedirectToTab tab="plan" />,
      },
      {
        path: "project/:projectId/export",
        element: <RedirectToTab tab="export" />,
      },
      {
        path: "project/:projectId/versions",
        element: <RedirectToTab tab="edit" />,
      },
    ],
  },

  // 兜底
  {
    path: "*",
    element: <NotFound />,
  },
];

export const appRouter = createBrowserRouter(appRoutes);