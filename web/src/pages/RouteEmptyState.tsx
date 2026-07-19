import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@/components/ui/empty";

type RouteEmptyStateProps = {
  title: string;
  notFound?: boolean;
};

export function RouteEmptyState({ title, notFound = false }: RouteEmptyStateProps) {
  return (
    <main className="flex min-h-[calc(100svh-7.5rem)]">
      <Empty>
        <EmptyHeader>
          <EmptyTitle>
            <h1>{title}</h1>
          </EmptyTitle>
          <EmptyDescription>
            {notFound
              ? "您访问的页面不存在或已移动。"
              : "该能力将在对应功能分支中实现；当前页面不连接后端服务。"}
          </EmptyDescription>
        </EmptyHeader>
        {notFound ? (
          <EmptyContent>
            <Button render={<Link to="/" />}>返回教学工作台</Button>
          </EmptyContent>
        ) : null}
      </Empty>
    </main>
  );
}
