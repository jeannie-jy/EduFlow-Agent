import { ArrowRight, GraduationCap, Presentation } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { Link } from "react-router-dom";

const audiencePaths = [
  {
    label: "学生",
    title: "我想理解一个知识点",
    description: "逐帧观察状态变化，修改一个关键参数，并把画布、讲解和状态表放在同一条阅读线上。",
    notes: ["选择公开案例", "比较参数结果", "回看关键帧"],
    action: "体验学生推演",
    href: "/explore/dijkstra",
    Icon: GraduationCap,
  },
  {
    label: "教师",
    title: "我想创建教学推演",
    description: "从知识点、课件或模板开始，确认教学计划后继续编辑、校对、局部重生成与导出。",
    notes: ["确认教学目标", "锁定有效内容", "发布多种成果"],
    action: "开始创建推演",
    href: "/app/new",
    Icon: Presentation,
  },
] as const;

export function AudienceSection() {
  const reduceMotion = useReducedMotion();

  return (
    <motion.section
      id="audiences"
      className="landing-chapter landing-audiences"
      aria-labelledby="audiences-heading"
      initial={reduceMotion ? false : { opacity: 1, y: 14 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.2 }}
      transition={{ duration: 0.56, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="landing-chapter__index"><span>CHAPTER</span><strong>03</strong></div>
      <div className="landing-chapter__body">
        <header className="landing-chapter__heading landing-audiences__heading">
          <p>使用场景 / 选择一条进入路径</p>
          <h2 id="audiences-heading">学习与教学，在这里各有起点</h2>
          <p className="landing-chapter__lede">两条路径共享同一份推演，只是从不同的问题开始阅读。</p>
        </header>
        <div className="landing-audiences__paths">
          {audiencePaths.map(({ label, title, description, notes, action, href, Icon }) => (
            <article key={label} className="landing-audience-path paper-surface">
              <div className="landing-audience-path__tab"><Icon aria-hidden="true" /><span>{label}：</span></div>
              <h3>{title}</h3>
              <p>{description}</p>
              <ul>{notes.map((note) => <li key={note}>{note}</li>)}</ul>
              <Link to={href} className="landing-inline-action interactive-lift">{action} <ArrowRight aria-hidden="true" /></Link>
            </article>
          ))}
        </div>
      </div>
    </motion.section>
  );
}
