import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";

export function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-6">
      <h1 className="text-6xl font-bold text-slate-200">404</h1>
      <p className="mt-4 text-lg text-slate-600">页面未找到</p>
      <p className="mt-2 text-sm text-slate-400">你访问的页面不存在或已被移动</p>
      <div className="mt-8 flex gap-4">
        <Link to="/">
          <Button variant="outline">返回首页</Button>
        </Link>
        <Link to="/app">
          <Button>进入工作台</Button>
        </Link>
      </div>
    </div>
  );
}