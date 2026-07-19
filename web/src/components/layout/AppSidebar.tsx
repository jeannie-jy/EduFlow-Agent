import {
  ArchiveIcon,
  BookOpenIcon,
  LayoutDashboardIcon,
  LibraryIcon,
  WaypointsIcon,
} from "lucide-react";
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
  { label: "工作台", href: "#workspace", icon: LayoutDashboardIcon },
  { label: "课程", href: "#courses", icon: BookOpenIcon },
  { label: "学习路径", href: "#paths", icon: WaypointsIcon },
  { label: "资源库", href: "#library", icon: LibraryIcon },
  { label: "归档", href: "#archive", icon: ArchiveIcon },
] as const;

export function AppSidebar() {
  const { state } = useSidebar();

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <a
          href="#workspace"
          className="flex h-10 items-center rounded-md px-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring"
          aria-label="EduFlow 工作台"
        >
          <EduFlowBrand compact={state === "collapsed"} />
        </a>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>教学空间</SidebarGroupLabel>
          <SidebarGroupContent>
            <nav aria-label="主导航">
              <SidebarMenu>
                {navigationItems.map(({ label, href, icon: Icon }, index) => (
                  <SidebarMenuItem key={label}>
                    <SidebarMenuButton
                      render={<a href={href} />}
                      isActive={index === 0}
                      tooltip={label}
                    >
                      <Icon />
                      <span>{label}</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
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
