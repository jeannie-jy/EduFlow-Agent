import { type CSSProperties, type PropsWithChildren } from "react";
import { useLocation } from "react-router-dom";
import { EllipsisIcon } from "lucide-react";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
} from "@/components/ui/breadcrumb";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { AppSidebar } from "./AppSidebar";
import { ThemeSwitcher } from "./ThemeSwitcher";

const routeLabels: Record<string, string> = {
  "/app": "我的推演",
  "/app/new": "新建推演",
  "/app/templates": "知识点模板库",
};

export function AppShell({ children }: PropsWithChildren) {
  const { pathname } = useLocation();
  const routeLabel = routeLabels[pathname] ?? "";

  return (
    <SidebarProvider
      style={{ "--sidebar-width": "14rem" } as CSSProperties}
      className="min-w-0 overflow-hidden"
    >
      <a
        href="#workspace"
        className="fixed top-3 left-3 z-50 -translate-y-16 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition-transform focus:translate-y-0 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
      >
        跳到工作区
      </a>
      <AppSidebar />
      <SidebarInset className="h-svh min-w-0 overflow-hidden">
        <header className="sticky top-0 z-30 flex h-15 w-full min-w-0 shrink-0 items-center justify-between gap-3 border-b bg-background/92 px-3 backdrop-blur-xl md:px-5">
          <div className="flex min-w-0 items-center gap-2.5">
            <SidebarTrigger aria-label="切换侧边栏" />
            <Separator orientation="vertical" className="h-4" />
            <Breadcrumb>
              <BreadcrumbList>
                <BreadcrumbItem>
                  <BreadcrumbPage className="truncate text-[15px] font-semibold tracking-[-0.01em]">
                    {routeLabel || "EduFlow"}
                  </BreadcrumbPage>
                </BreadcrumbItem>
                {!routeLabel && (
                  <BreadcrumbItem>
                    <BreadcrumbPage className="truncate text-[15px] text-muted-foreground">
                      项目详情
                    </BreadcrumbPage>
                  </BreadcrumbItem>
                )}
              </BreadcrumbList>
            </Breadcrumb>
          </div>
          <div className="flex items-center gap-2">
            <ThemeSwitcher />
            <Button variant="outline" size="icon" aria-label="更多操作">
              <EllipsisIcon />
            </Button>
          </div>
        </header>
        <div
          id="workspace"
          tabIndex={-1}
          className="min-h-0 min-w-0 flex-1 overflow-x-hidden overflow-y-auto p-2.5 md:p-3"
        >
          {children}
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}