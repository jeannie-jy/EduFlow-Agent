import {
  DownloadIcon,
  LayoutDashboardIcon,
  LayoutTemplateIcon,
  PencilRulerIcon,
  SparklesIcon,
} from "lucide-react";
import { matchPath, NavLink, useLocation } from "react-router-dom";
import { EduFlowBrand } from "@/components/brand/EduFlowBrand";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
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
  { label: "工作台", to: "/", icon: LayoutDashboardIcon, end: true },
  { label: "新建推演", to: "/new", icon: SparklesIcon, end: false },
  { label: "教师编辑器", to: "/project/demo/edit", icon: PencilRulerIcon, end: false },
  { label: "模板库", to: "/templates", icon: LayoutTemplateIcon, end: false },
  { label: "导出中心", to: "/project/demo/export", icon: DownloadIcon, end: false },
] as const;

export function AppSidebar() {
  const { state, isMobile, setOpenMobile } = useSidebar();
  const { pathname } = useLocation();

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <NavLink
          to="/"
          className="flex min-h-11 items-center rounded-md px-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring"
          aria-label="EduFlow 工作台"
        >
          <EduFlowBrand compact={state === "collapsed"} />
        </NavLink>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>教学空间</SidebarGroupLabel>
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
      </SidebarContent>
      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              size="lg"
              tooltip="教师账户"
              aria-label="教师账户"
            >
              <Avatar size="sm">
                <AvatarFallback>教</AvatarFallback>
              </Avatar>
              <span className="flex min-w-0 flex-1 flex-col items-start gap-0.5">
                <span className="truncate font-medium">教师工作区</span>
                <Badge variant="secondary">教师</Badge>
              </span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
