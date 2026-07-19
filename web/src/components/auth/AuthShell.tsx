import { ArrowLeft, CheckCircle2 } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { EduFlowBrand } from "../brand/EduFlowBrand";
import { BookHeroScene } from "../effects/BookHeroScene";

export function AuthShell({ children }: { children: ReactNode }) {
  return (
    <main className="auth-page">
      <section className="auth-visual" aria-label="EduFlow 品牌介绍">
        <div className="auth-visual__top"><EduFlowBrand /></div>
        <div className="auth-visual__copy">
          <p className="eyebrow eyebrow--light">知识从这里开始流动</p>
          <h2>每一步变化，<br />都值得被看见。</h2>
          <p>把抽象概念转化为可以播放、回退和探索的教学推演。</p>
          <ul>
            <li><CheckCircle2 /> 自动组织教学路径</li>
            <li><CheckCircle2 /> 逐帧观察状态变化</li>
          </ul>
        </div>
        <BookHeroScene compact />
      </section>
      <section className="auth-panel">
        <Link className="auth-back" to="/"><ArrowLeft size={17} /> 返回首页</Link>
        <div className="auth-panel__inner">{children}</div>
      </section>
    </main>
  );
}
