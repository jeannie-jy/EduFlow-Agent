import { createBrowserRouter, Navigate, Outlet, useLocation, useParams, type RouteObject } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { useAuth } from "@/lib/auth";

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

function ProtectedAppLayout() {
  const location = useLocation();
  const { state, status, retry } = useAuth();

  if (status === "checking") {
    return <div className="flex min-h-svh items-center justify-center text-sm text-muted-foreground">正在验证登录状态…</div>;
  }

  if (status === "unavailable") {
    return (
      <main className="flex min-h-svh flex-col items-center justify-center gap-3 p-6 text-center">
        <h1 className="text-lg font-semibold">暂时无法验证登录状态</h1>
        <p className="text-sm text-muted-foreground">服务器暂时不可用，请确认后端已启动后重试。</p>
        <button type="button" className="rounded-md border px-3 py-2 text-sm" onClick={retry}>重试</button>
      </main>
    );
  }

  if (!state?.isAuthenticated) {
    const next = `${location.pathname}${location.search}${location.hash}`;
    return <Navigate to={`/login?reason=auth&next=${encodeURIComponent(next)}`} replace />;
  }

  return <AppLayout />;
}

function AdminRoute() {
  return useAuth().state?.role === "admin" ? <Outlet /> : <Navigate to="/app" replace />;
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
  {
    path: "/verify-email",
    lazy: lazyComponent(() => import("@/features/auth/AccountRecoveryPages"), "VerifyEmailPage"),
  },
  {
    path: "/forgot-password",
    lazy: lazyComponent(() => import("@/features/auth/AccountRecoveryPages"), "ForgotPasswordPage"),
  },
  {
    path: "/reset-password",
    lazy: lazyComponent(() => import("@/features/auth/AccountRecoveryPages"), "ResetPasswordPage"),
  },
  {
    path: "/privacy",
    lazy: lazyComponent(() => import("@/pages/LegalPages"), "PrivacyPage"),
  },
  {
    path: "/terms",
    lazy: lazyComponent(() => import("@/pages/LegalPages"), "TermsPage"),
  },

  // 应用路由（包裹 AppShell）
  {
    path: "/app",
    element: <ProtectedAppLayout />,
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
        path: "settings",
        lazy: lazyComponent(() => import("@/pages/AccountSettingsPage"), "AccountSettingsPage"),
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
