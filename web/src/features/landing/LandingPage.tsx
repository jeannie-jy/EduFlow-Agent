import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { EduFlowBrand } from "@/components/brand/EduFlowBrand";
import { ArrowRight, WandSparkles, Braces, Film, Route } from "lucide-react";

const capabilities = [
  {
    icon: WandSparkles,
    title: "智能规划",
    desc: "从一句话生成教学计划，自动组织学习目标、先修知识与教学步骤。",
  },
  {
    icon: Braces,
    title: "交互推演",
    desc: "把抽象算法过程变成可播放、暂停、回退的逐帧推演。",
  },
  {
    icon: Film,
    title: "多端输出",
    desc: "保留互动版本用于探索，也能导出视频用于课堂演示与复习。",
  },
];

const steps = [
  { step: "01", title: "提出你想理解的问题", desc: "用自然语言描述主题、受众和讲解重点。" },
  { step: "02", title: "AI 编排知识与画面", desc: "教学计划、参数和逐帧场景在同一条推理流中生成。" },
  { step: "03", title: "播放、探索，再带走", desc: "调整参数观察变化，保存推演或导出教学素材。" },
];

export function LandingPage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
      {/* Header */}
      <header className="fixed top-0 inset-x-0 z-50 border-b border-slate-200/60 bg-white/80 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <EduFlowBrand />
          <nav className="flex items-center gap-6">
            <Link to="/login" className="text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors">
              登录
            </Link>
            <Link to="/register">
              <Button size="sm">免费注册</Button>
            </Link>
          </nav>
        </div>
      </header>

      <main>
        {/* Hero */}
        <section className="relative pt-32 pb-20 px-6">
          <div className="mx-auto max-w-4xl text-center">
            <p className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-indigo-50 px-4 py-1.5 text-xs font-semibold text-indigo-600 mb-6">
              <WandSparkles size={14} />
              AI 驱动的交互式教学推演
            </p>
            <h1 className="text-5xl font-bold tracking-tight text-slate-900 sm:text-6xl">
              让知识动起来
              <br />
              <span className="bg-gradient-to-r from-indigo-600 to-violet-600 bg-clip-text text-transparent">
                让理解自然发生
              </span>
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-lg text-slate-500 leading-relaxed">
              EduFlow 将算法、数据结构与系统过程转化为可播放、可回退、可调整参数的逐帧学习体验。
            </p>
            <div className="mt-10 flex items-center justify-center gap-4">
              <Link to="/register">
                <Button size="lg" className="gap-2">
                  免费开始 <ArrowRight size={18} />
                </Button>
              </Link>
              <a href="#how-it-works">
                <Button variant="outline" size="lg">
                  了解更多
                </Button>
              </a>
            </div>
            <div className="mt-10 flex items-center justify-center gap-2 text-sm text-slate-400">
              <Route size={17} className="text-indigo-400" />
              <span>从问题到推演，只需一条清晰路径</span>
            </div>
          </div>
        </section>

        {/* 能力卡片 */}
        <section className="px-6 pb-20">
          <div className="mx-auto grid max-w-5xl gap-6 sm:grid-cols-3">
            {capabilities.map(({ icon: Icon, title, desc }) => (
              <div
                key={title}
                className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition-shadow hover:shadow-md"
              >
                <div className="mb-4 flex size-11 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
                  <Icon size={22} />
                </div>
                <h3 className="mb-2 text-lg font-semibold text-slate-900">{title}</h3>
                <p className="text-sm text-slate-500 leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* 三步流程 */}
        <section id="how-it-works" className="bg-slate-50 px-6 py-20">
          <div className="mx-auto max-w-4xl text-center">
            <p className="text-sm font-semibold text-indigo-600 mb-3">三步进入知识现场</p>
            <h2 className="text-3xl font-bold text-slate-900 mb-4">每一次学习，都有一条看得见的路径</h2>
            <p className="text-slate-500 mb-12">
              不用从空白画布开始。把你的问题组织成可以理解、验证和分享的教学过程。
            </p>
            <div className="grid gap-8 sm:grid-cols-3">
              {steps.map(({ step, title, desc }) => (
                <div key={step} className="text-left">
                  <span className="text-3xl font-bold text-indigo-200">{step}</span>
                  <h3 className="mt-2 text-lg font-semibold text-slate-900">{title}</h3>
                  <p className="mt-1 text-sm text-slate-500">{desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* 适用场景 */}
        <section className="px-6 py-16">
          <div className="mx-auto flex max-w-3xl flex-wrap items-center justify-center gap-3 text-sm text-slate-400">
            <span className="rounded-full bg-slate-100 px-3 py-1 text-slate-600">算法与数据结构</span>
            <span className="text-slate-300">·</span>
            <span className="rounded-full bg-slate-100 px-3 py-1 text-slate-600">操作系统过程</span>
            <span className="text-slate-300">·</span>
            <span className="rounded-full bg-slate-100 px-3 py-1 text-slate-600">网络协议交互</span>
            <span className="text-slate-300">·</span>
            <span className="rounded-full bg-slate-100 px-3 py-1 text-slate-600">课堂演示与复习</span>
          </div>
        </section>

        {/* CTA */}
        <section className="bg-slate-900 px-6 py-20 text-center">
          <h2 className="text-3xl font-bold text-white mb-4">准备好开始了吗？</h2>
          <p className="text-slate-400 mb-8">把你正在思考的知识点，交给 EduFlow。</p>
          <Link to="/register">
            <Button size="lg" className="gap-2">
              创建免费账号 <ArrowRight size={18} />
            </Button>
          </Link>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 px-6 py-8">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <EduFlowBrand compact />
          <p className="text-sm text-slate-400">© 2026 EduFlow</p>
        </div>
      </footer>
    </div>
  );
}