import { ArrowRight, BookmarkCheck } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { Link } from "react-router-dom";

export function FinalActionSection() {
  const reduceMotion = useReducedMotion();

  return (
    <motion.section
      className="landing-final-action"
      aria-labelledby="final-action-heading"
      initial={reduceMotion ? false : { opacity: 1, y: 14 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.2 }}
      transition={{ duration: 0.56, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="landing-final-action__seal"><BookmarkCheck aria-hidden="true" /><span>READY TO BEGIN</span></div>
      <div>
        <p>最后一页 / 从问题开始</p>
        <h2 id="final-action-heading">从一个你正在讲授或学习的知识点开始。</h2>
        <p>给出一个概念、一个目标，或从模板库拿起第一份底稿；其余的步骤会按教学逻辑展开。</p>
      </div>
      <div className="landing-final-action__actions">
        <Link to="/app/project/_new" className="landing-action landing-action--primary interactive-lift">开始一场新推演 <ArrowRight aria-hidden="true" /></Link>
        <Link to="/explore/dijkstra" className="landing-text-link">先体验一个案例 <ArrowRight aria-hidden="true" /></Link>
      </div>
    </motion.section>
  );
}
