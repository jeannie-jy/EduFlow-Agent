import { createBrowserRouter, Outlet, type RouteObject } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { WorkbenchPage } from "@/components/workbench/WorkbenchPage";
import { RouteEmptyState } from "@/pages/RouteEmptyState";

function ShellRoute() {
  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}

export const appRoutes: RouteObject[] = [
  {
    element: <ShellRoute />,
    children: [
      { index: true, element: <WorkbenchPage /> },
      { path: "new", element: <RouteEmptyState title="新建推演" /> },
      {
        path: "project/demo/plan",
        element: <RouteEmptyState title="教学计划确认" />,
      },
      {
        path: "project/demo/edit",
        element: <RouteEmptyState title="教师编辑器" />,
      },
      {
        path: "project/demo/play",
        element: <RouteEmptyState title="交互式播放器" />,
      },
      {
        path: "project/demo/export",
        element: <RouteEmptyState title="导出中心" />,
      },
      { path: "templates", element: <RouteEmptyState title="知识点模板库" /> },
      { path: "*", element: <RouteEmptyState title="页面未找到" notFound /> },
    ],
  },
];

export const appRouter = createBrowserRouter(appRoutes);
