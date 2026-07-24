import { ArrowRight, Clock3, Layers3 } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { Link } from "react-router-dom";
import { templates } from "../landing-content";

export function TemplateSection() {
  const reduceMotion = useReducedMotion();

  return (
    <motion.section
      id="templates"
      className="landing-chapter landing-templates"
      aria-labelledby="templates-heading"
      initial={reduceMotion ? false : { opacity: 1, y: 14 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.2 }}
      transition={{ duration: 0.56, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="landing-chapter__index"><span>CHAPTER</span><strong>05</strong></div>
      <div className="landing-chapter__body">
        <header className="landing-chapter__heading">
          <p>模板库 / 已完成的起草稿</p>
          <h2 id="templates-heading">不必从空白开始</h2>
          <p className="landing-chapter__lede">从一个经过整理的案例起笔，再把它改成自己的课堂、作业或复习路径。</p>
        </header>
        <div className="landing-templates__shelf">
          {templates.map(([name, category, frames, duration], index) => (
            <article key={name} className="landing-template paper-surface">
              <div className="landing-template__folio"><span>CASE / 0{index + 1}</span><b>{category}</b></div>
              <h3>{name}</h3>
              <div className="landing-template__metadata"><span><Layers3 aria-hidden="true" />{frames}</span><span><Clock3 aria-hidden="true" />{duration}</span></div>
              <p>{name === "Dijkstra" ? "从源点出发，观察距离表与最短路径如何同时收敛。" : name === "冒泡排序" ? "让每一次比较与交换都留下可讲解、可回看的依据。" : "用时间片推进进程队列，读清调度策略带来的变化。"}</p>
              <div className="landing-template__actions">
                <Link to="/explore/dijkstra" className="landing-text-link">体验案例 <ArrowRight aria-hidden="true" /></Link>
                <Link to={`/app/new?template=${encodeURIComponent(name)}`} className="landing-text-link">基于模板创建 <ArrowRight aria-hidden="true" /></Link>
              </div>
            </article>
          ))}
        </div>
      </div>
    </motion.section>
  );
}
