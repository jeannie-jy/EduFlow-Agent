import {
  BookOpenIcon,
  CirclePlayIcon,
  DownloadIcon,
  FileClockIcon,
  FolderClockIcon,
  GraduationCapIcon,
  LayoutTemplateIcon,
  PencilRulerIcon,
  PlusIcon,
} from "lucide-react";
import { matchPath, NavLink, useLocation } from "react-router-dom";
import { EduFlowBrand } from "@/components/brand/EduFlowBrand";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar";

const navigationItems = [
  { label: "教学路径", to: "/app/project/demo/plan", icon: GraduationCapIcon, end: false },
  { label: "互动推演", to: "/app", icon: CirclePlayIcon, end: true },
  { label: "模板库", to: "/app/templates", icon: LayoutTemplateIcon, end: false },
  { label: "教师编辑器", to: "/app/project/demo/edit", icon: PencilRulerIcon, end: false },
  { label: "导出中心", to: "/app/project/demo/export", icon: DownloadIcon, end: false },
] as const;

const recentItems = [
  { label: "Dijkstra 最短路径", time: "刚刚" },
  { label: "Prim 最小生成树", time: "昨天" },
  { label: "拓扑排序", time: "2 天前" },
  { label: "BFS 广度优先搜索", time: "3 天前" },
];

export function AppSidebar() {
  const { state, isMobile, setOpenMobile } = useSidebar();
  const { pathname } = useLocation();

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="gap-3 border-b border-sidebar-border/70 p-3">
        <NavLink
          to="/app"
          className="flex min-h-11 items-center rounded-md px-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring"
          aria-label="EduFlow 工作台"
        >
          <EduFlowBrand compact={state === "collapsed"} />
        </NavLink>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              render={<NavLink to="/app/new" aria-label="新建推演" />}
              className="min-h-10 bg-sidebar-primary text-sidebar-primary-foreground hover:bg-sidebar-primary/90 hover:text-sidebar-primary-foreground"
            >
              <PlusIcon />
              <span>新建推演</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>工作区</SidebarGroupLabel>
          <SidebarGroupContent>
            <nav aria-label="主导航">
              <SidebarMenu>
                {navigationItems.map(({ label, to, icon: Icon, ...item }) => {
                  const isActive = Boolean(
                    matchPath({ path: to, end: item.end }, pathname),
                  );

                  return (
                  <SidebarMenuItem key={label}>
                    <SidebarMenuButton
                      render={
                        <NavLink
                          to={to}
                          end={item.end}
                          title={state === "collapsed" ? label : undefined}
                          onClick={() => {
                            if (isMobile) setOpenMobile(false);
                          }}
                        />
                      }
                      isActive={isActive}
                      className="min-h-11 group-data-[collapsible=icon]:size-11!"
                    >
                      <Icon />
                      <span>{label}</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                  );
                })}
              </SidebarMenu>
            </nav>
          </SidebarGroupContent>
        </SidebarGroup>
        <SidebarGroup>
          <SidebarGroupLabel>最近推演</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {recentItems.map((item, index) => (
                <SidebarMenuItem key={item.label}>
                  <SidebarMenuButton
                    render={<NavLink to={index === 0 ? "/app" : "/app/project/demo/play"} title={state === "collapsed" ? item.label : undefined} />}
                    isActive={index === 0 && pathname === "/app"}
                    className="min-h-10"
                  >
                    {index === 0 ? <FolderClockIcon /> : <FileClockIcon />}
                    <span className="min-w-0 flex-1 truncate">{item.label}</span>
                    <span className="text-[10px] text-sidebar-foreground/55">{item.time}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              size="lg"
              tooltip="计算机科学与技术"
              aria-label="当前课程：计算机科学与技术"
            >
              <Avatar size="sm">
                <AvatarFallback className="bg-primary/12 text-primary">CS</AvatarFallback>
              </Avatar>
              <span className="flex min-w-0 flex-1 flex-col items-start gap-0.5">
                <span className="truncate font-medium">计算机科学与技术</span>
                <span className="text-xs text-sidebar-foreground/55">本科 2022 级</span>
              </span>
              <BookOpenIcon className="text-sidebar-foreground/50" />
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}