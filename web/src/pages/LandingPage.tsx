import { ArrowRight, Braces, Film, Route, Sparkles, WandSparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { EduFlowBrand } from "../components/brand/EduFlowBrand";
import { BookHeroScene } from "../components/effects/BookHeroScene";
import { PublicHeader } from "../components/layout/PublicHeader";

const capabilities = [
  { icon: WandSparkles, kicker: "01 · 理解意图", title: "从一句话生成教学计划", copy: "把学习目标、先修知识与教学步骤自动组织为清晰路径。", meta: "智能规划" },
  { icon: Braces, kicker: "02 · 看见变化", title: "把抽象过程变成逐帧推演", copy: "算法状态、数据结构与系统过程都能播放、暂停和回退。", meta: "交互推演" },
  { icon: Film, kicker: "03 · 自由使用", title: "从探索体验延伸到教学视频", copy: "保留互动版本，也能导出适合课堂与复习的演示内容。", meta: "多端输出" },
];

const steps = [
  { number: "01", title: "提出你想理解的问题", copy: "用自然语言描述主题、受众和讲解重点。" },
  { number: "02", title: "AI 编排知识与画面", copy: "教学计划、参数和逐帧场景在同一条推理流中生成。" },
  { number: "03", title: "播放、探索，再带走", copy: "调整参数观察变化，保存推演或导出教学素材。" },
];

export function LandingPage() {
  return (
    <div className="landing-page">
      <PublicHeader />
      <main>
        <section className="hero" aria-labelledby="hero-title">
          <div className="hero__ambient" aria-hidden="true" />
          <div className="hero__content">
            <p className="eyebrow"><Sparkles size={15} /> AI 驱动的交互式教学推演</p>
            <h1 id="hero-title">让知识动起来。<br /><span>让理解自然发生。</span></h1>
            <p className="hero__copy">EduFlow 将算法、数据结构与系统过程转化为可播放、可回退、可调整参数的逐帧学习体验。</p>
            <div className="hero__actions">
              <Link className="button" to="/register">免费开始 <ArrowRight size={18} /></Link>
              <a className="button button--ghost" href="#how-it-works">查看如何工作</a>
            </div>
            <div className="hero__proof" aria-label="平台能力摘要">
              <span className="proof-orbit"><Route size={17} /></span>
              <span><strong>从问题到推演，只需一条清晰路径</strong><small>适合学生自学，也适合教师备课</small></span>
            </div>
          </div>
          <BookHeroScene />
        </section>

        <section className="capability-section" id="capabilities" aria-label="把复杂知识变成可以触摸的学习流">
          <div className="capability-grid">
            {capabilities.map(({ icon: Icon, kicker, title, copy, meta }) => (
              <article className="capability-card" key={title}>
                <div className="capability-card__top"><span className="capability-icon"><Icon /></span><span>{meta}</span></div>
                <p className="capability-card__kicker">{kicker}</p>
                <h3>{title}</h3>
                <p>{copy}</p>
                <div className="capability-card__preview" aria-hidden="true">
                  <span /><span /><span /><i />
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="workflow" id="how-it-works" aria-labelledby="workflow-title">
          <div className="workflow__intro">
            <p className="eyebrow">三步进入知识现场</p>
            <h2 id="workflow-title">每一次学习，都有一条看得见的路径</h2>
            <p>不用从空白画布开始。EduFlow 会把你的问题组织成可以理解、验证和分享的教学过程。</p>
          </div>
          <div className="workflow__steps">
            {steps.map((step) => (
              <article className="workflow-step" key={step.number}>
                <span>{step.number}</span><div><h3>{step.title}</h3><p>{step.copy}</p></div>
              </article>
            ))}
          </div>
        </section>

        <section className="scenario-strip" id="scenarios" aria-label="使用场景">
          <p>算法与数据结构</p><span /> <p>操作系统过程</p><span /> <p>网络协议交互</p><span /> <p>课堂演示与复习</p>
        </section>

        <section className="final-cta">
          <p className="eyebrow">下一次理解，从这里开始</p>
          <h2>把你正在思考的知识点，交给 EduFlow</h2>
          <p>从一句问题开始，获得一段可以播放、探索和分享的学习过程。</p>
          <Link className="button button--light" to="/register">创建免费账号 <ArrowRight size={18} /></Link>
        </section>
      </main>
      <footer className="public-footer"><EduFlowBrand /><p>让复杂知识清晰流动。</p><span>© 2026 EduFlow</span></footer>
    </div>
  );
}
