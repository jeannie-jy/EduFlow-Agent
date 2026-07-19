import type { PropsWithChildren } from "react";
import { useLocation } from "react-router-dom";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
} from "@/components/ui/breadcrumb";
import { Separator } from "@/components/ui/separator";
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { AppSidebar } from "./AppSidebar";
import { ThemeSwitcher } from "./ThemeSwitcher";

const routeLabels: Record<string, string> = {
  "/": "教学工作台",
  "/new": "新建推演",
  "/project/demo/plan": "教学计划确认",
  "/project/demo/edit": "教师编辑器",
  "/project/demo/play": "交互式播放器",
  "/project/demo/export": "导出中心",
  "/templates": "知识点模板库",
};

export function AppShell({ children }: PropsWithChildren) {
  const { pathname } = useLocation();
  const routeLabel = routeLabels[pathname] ?? "页面未找到";

  return (
    <SidebarProvider>
      <a
        href="#workspace"
        className="fixed top-3 left-3 z-50 -translate-y-16 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition-transform focus:translate-y-0 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
      >
        跳到工作区
      </a>
      <AppSidebar />
      <SidebarInset>
        <header className="sticky top-0 flex h-14 shrink-0 items-center justify-between gap-3 border-b bg-background/95 px-4 backdrop-blur-sm">
          <div className="flex min-w-0 items-center gap-2">
            <SidebarTrigger aria-label="切换侧边栏" />
            <Separator orientation="vertical" className="h-4" />
            <Breadcrumb>
              <BreadcrumbList>
                <BreadcrumbItem>
                  <BreadcrumbPage>{routeLabel}</BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
          </div>
          <ThemeSwitcher />
        </header>
        <div id="workspace" tabIndex={-1} className="min-h-0 flex-1 p-4 md:p-6">
          {children}
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}
