import { motion, useReducedMotion } from "motion/react";
import { processSteps } from "../landing-content";

export function HowItWorksSection() {
  const reduceMotion = useReducedMotion();

  return (
    <motion.section
      id="product"
      className="landing-chapter landing-process"
      aria-labelledby="how-it-works-heading"
      initial={reduceMotion ? false : { opacity: 1, y: 14 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.2 }}
      transition={{ duration: 0.56, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="landing-chapter__index"><span>CHAPTER</span><strong>02</strong></div>
      <div className="landing-chapter__body">
        <header className="landing-chapter__heading">
          <p>产品原理 / 一条可校对的教学链路</p>
          <h2 id="how-it-works-heading">从一个问题，到一场完整推演</h2>
          <p className="landing-chapter__lede">每一份内容先被理解、再被编排；每一帧变化都有可回看的教学理由。</p>
        </header>
        <ol className="landing-process__ledger" aria-label="教学推演的五个步骤">
          {processSteps.map(([title, description], index) => (
            <li key={title}>
              <span className="landing-process__number">0{index + 1}</span>
              <div><h3>{title}</h3><p>{description}</p></div>
            </li>
          ))}
        </ol>
      </div>
    </motion.section>
  );
}
