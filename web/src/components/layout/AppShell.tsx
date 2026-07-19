import { useState, type CSSProperties, type PropsWithChildren } from "react";
import { useLocation } from "react-router-dom";
import { EllipsisIcon, PencilIcon, RefreshCwIcon, Share2Icon } from "lucide-react";
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
  const [shareState, setShareState] = useState("分享");
  const isWorkbench = pathname === "/";

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
                    {isWorkbench ? "Dijkstra 最短路径" : routeLabel}
                  </BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
            {isWorkbench ? (
              <Button variant="ghost" size="icon-sm" aria-label="重命名推演">
                <PencilIcon />
              </Button>
            ) : null}
          </div>
          <div className="flex items-center gap-2">
            {isWorkbench ? (
              <>
                <Button
                  variant="outline"
                  className="hidden sm:inline-flex"
                  onClick={() => window.dispatchEvent(new Event("eduflow:regenerate"))}
                >
                  <RefreshCwIcon data-icon="inline-start" />
                  重新生成
                </Button>
                <Button
                  variant="outline"
                  className="hidden md:inline-flex"
                  onClick={() => {
                    setShareState("已复制");
                    window.setTimeout(() => setShareState("分享"), 1600);
                  }}
                >
                  <Share2Icon data-icon="inline-start" />
                  {shareState}
                </Button>
              </>
            ) : null}
            <ThemeSwitcher />
            <Button variant="outline" size="icon" aria-label="更多操作">
              <EllipsisIcon />
            </Button>
          </div>
        </header>
        <div
          id="workspace"
          tabIndex={-1}
          className="min-h-0 min-w-0 flex-1 overflow-x-hidden overflow-y-auto p-2.5 md:p-3 lg:overflow-hidden"
        >
          {children}
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}
