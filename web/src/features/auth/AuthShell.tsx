import { ArrowLeft, CheckCircle2 } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { EduFlowBrand } from "@/components/brand/EduFlowBrand";

export function AuthShell({ children }: { children: ReactNode }) {
  return (
    <main className="flex min-h-screen">
      {/* 左侧品牌区 */}
      <section className="hidden w-[480px] flex-col justify-between bg-gradient-to-br from-[#315E59] via-[#294E49] to-[#203B37] p-12 text-[#FFF8E8] lg:flex">
        <div className="[&_img]:brightness-0 [&_img]:invert">
          <EduFlowBrand />
        </div>
        <div>
          <p className="mb-4 text-sm font-semibold uppercase tracking-wider text-[#C8D9D0]">
            知识从这里开始流动
          </p>
          <h2 className="text-3xl font-bold leading-tight mb-4">
            每一步变化，
            <br />
            都值得被看见。
          </h2>
          <p className="leading-relaxed text-[#DDE5D8]">
            把抽象概念转化为可以播放、回退和探索的教学推演。
          </p>
          <ul className="mt-8 space-y-3">
            <li className="flex items-center gap-2 text-sm">
              <CheckCircle2 size={18} className="text-[#AFC9BD]" />
              自动组织教学路径
            </li>
            <li className="flex items-center gap-2 text-sm">
              <CheckCircle2 size={18} className="text-[#AFC9BD]" />
              逐帧观察状态变化
            </li>
            <li className="flex items-center gap-2 text-sm">
              <CheckCircle2 size={18} className="text-[#AFC9BD]" />
              导出教学视频素材
            </li>
          </ul>
        </div>
        <p className="text-xs text-[#AFC9BD]">© 2026 EduFlow</p>
      </section>

      {/* 右侧表单区 */}
      <section className="flex flex-1 items-center justify-center px-6">
        <div className="w-full max-w-md">
          <Link
            to="/"
            className="mb-8 inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
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
