import { ArrowLeft, CheckCircle2 } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { EduFlowBrand } from "@/components/brand/EduFlowBrand";

export function AuthShell({ children }: { children: ReactNode }) {
  return (
    <main className="flex min-h-screen">
      {/* 左侧品牌区 */}
      <section className="hidden w-[480px] flex-col justify-between bg-gradient-to-br from-indigo-600 to-violet-700 p-12 text-white lg:flex">
        <EduFlowBrand />
        <div>
          <p className="text-sm font-semibold uppercase tracking-wider text-indigo-200 mb-4">
            知识从这里开始流动
          </p>
          <h2 className="text-3xl font-bold leading-tight mb-4">
            每一步变化，
            <br />
            都值得被看见。
          </h2>
          <p className="text-indigo-200 leading-relaxed">
            把抽象概念转化为可以播放、回退和探索的教学推演。
          </p>
          <ul className="mt-8 space-y-3">
            <li className="flex items-center gap-2 text-sm">
              <CheckCircle2 size={18} className="text-indigo-300" />
              自动组织教学路径
            </li>
            <li className="flex items-center gap-2 text-sm">
              <CheckCircle2 size={18} className="text-indigo-300" />
              逐帧观察状态变化
            </li>
            <li className="flex items-center gap-2 text-sm">
              <CheckCircle2 size={18} className="text-indigo-300" />
              导出教学视频素材
            </li>
          </ul>
        </div>
        <p className="text-xs text-indigo-300">© 2026 EduFlow</p>
      </section>

      {/* 右侧表单区 */}
      <section className="flex flex-1 items-center justify-center px-6">
        <div className="w-full max-w-md">
          <Link
            to="/"
            className="mb-8 inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 transition-colors"
          >
            <ArrowLeft size={17} />
            返回首页
          </Link>
          {children}
        </div>
      </section>
    </main>
  );
}