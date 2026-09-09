import { createBrowserRouter, Navigate, Outlet, useParams, type RouteObject } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { getAuthState } from "@/lib/auth";

// 公开页面
import { LandingPage } from "@/features/landing/LandingPage";

const lazyComponent = <T extends Record<string, unknown>, K extends keyof T>(
  loader: () => Promise<T>,
  exportName: K,
) => async () => ({ Component: (await loader())[exportName] as React.ComponentType });

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

function AdminRoute() {
  return getAuthState()?.role === "admin" ? <Outlet /> : <Navigate to="/app" replace />;
}

// ── 路由 ────────────────────────────────────────────────────

export const appRoutes: RouteObject[] = [
  // 公开路由（无 AppShell）
  {
    path: "/",
    element: <LandingPage />,
  },
  {
    path: "/explore/dijkstra",
    lazy: lazyComponent(
      () => import("@/features/explore/DijkstraExplorePage"),
      "DijkstraExplorePage",
    ),
  },
  {
    path: "/login",
    lazy: lazyComponent(() => import("@/features/auth/LoginPage"), "LoginPage"),
  },
  {
    path: "/register",
    lazy: lazyComponent(() => import("@/features/auth/RegisterPage"), "RegisterPage"),
  },

  // 应用路由（包裹 AppShell）
  {
    path: "/app",
    element: <AppLayout />,
    children: [
      {
        index: true,
        lazy: lazyComponent(() => import("@/pages/Dashboard"), "Dashboard"),
      },
      { path: "new", element: <Navigate to="/app/project/_new" replace /> },
      {
        path: "templates",
        lazy: lazyComponent(() => import("@/pages/TemplateBrowser"), "TemplateBrowser"),
      },
      {
        element: <AdminRoute />,
        children: [
          {
            path: "admin/users",
            lazy: lazyComponent(() => import("@/pages/AdminUsersPage"), "AdminUsersPage"),
          },
        ],
      },

      // 统一项目工作区
      {
        path: "project/:projectId",
        lazy: lazyComponent(() => import("@/pages/ProjectWorkspace"), "ProjectWorkspace"),
      },

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
    lazy: lazyComponent(() => import("@/pages/NotFound"), "NotFound"),
  },
];

export const appRouter = createBrowserRouter(appRoutes);
