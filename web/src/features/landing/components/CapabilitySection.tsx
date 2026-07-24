import { CheckCircle2, FileOutput, Gauge, PencilLine, Route, ScanSearch } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";

const capabilities = [
  ["教学规划", "把知识目标、先修概念与常见误区整理成可确认的教学顺序。", Route],
  ["逐帧推演", "用连续帧呈现状态如何变化，让关键步骤可以暂停、回看和比较。", Gauge],
  ["参数实验", "保留一个安全变量，观察输入变化如何影响路径、排序或时间线。", ScanSearch],
  ["教师编辑", "确认计划、锁定有效段落，并只对需要的部分重新生成。", PencilLine],
  ["多端输出", "把完成的推演整理为交互页面、讲解文本、字幕和视频。", FileOutput],
] as const;

const qualityChecks = ["知识正确性检查", "帧间状态一致性", "教学清晰度评估", "人工确认与局部重生成", "历史版本回退"] as const;

export function CapabilitySection() {
  const reduceMotion = useReducedMotion();

  return (
    <motion.section
      className="landing-chapter landing-capabilities"
      aria-labelledby="capabilities-heading"
      initial={reduceMotion ? false : { opacity: 1, y: 14 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.2 }}
      transition={{ duration: 0.56, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="landing-chapter__index"><span>CHAPTER</span><strong>04</strong></div>
      <div className="landing-chapter__body">
        <div className="landing-capabilities__layout">
          <header className="landing-chapter__heading">
            <p>能力与质量 / 不只生成，也能校对</p>
            <h2 id="capabilities-heading">教学内容值得被认真校对</h2>
            <p className="landing-chapter__lede">功能不是孤立的按钮，而是一套从教学意图到稳定输出的工作底稿。</p>
          </header>
          <aside className="landing-quality-note paper-surface" aria-label="质量校对单">
            <p>QUALITY CHECK / 05</p>
            <h3>每一步都留有检查点</h3>
            <ul>{qualityChecks.map((check) => <li key={check}><CheckCircle2 aria-hidden="true" />{check}</li>)}</ul>
          </aside>
        </div>
        <div className="landing-capabilities__ledger">
          {capabilities.map(([title, description, Icon], index) => (
            <article key={title}>
              <span>0{index + 1}</span>
              <Icon aria-hidden="true" />
              <div><h3>{title}</h3><p>{description}</p></div>
            </article>
          ))}
        </div>
      </div>
    </motion.section>
  );
}
