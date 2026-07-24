import { lazy, Suspense } from "react";
import { ArrowRight, BookOpenText } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { Link } from "react-router-dom";
import { heroContent, heroExamples } from "../landing-content";

const LazyDijkstraDemo = lazy(() =>
  import("@/features/demo/DijkstraDemo").then(({ DijkstraDemo }) => ({ default: DijkstraDemo })),
);

const reveal = {
  hidden: { opacity: 1, y: 14 },
  visible: { opacity: 1, y: 0 },
};

type HeroSectionProps = {
  isAuthenticated: boolean;
};

export function HeroSection({ isAuthenticated }: HeroSectionProps) {
  const reduceMotion = useReducedMotion();

  return (
    <>
      <section className="landing-hero" aria-labelledby="landing-hero-title">
        <aside className="landing-hero__chapter-rail" aria-label="章节 01：AI 教学推演平台">
          <span>CHAPTER</span>
          <strong>01</strong>
          <i />
          <p>AI 教学推演平台</p>
        </aside>

        <div className="landing-hero__content">
          <div className="landing-hero__headline-band">
            <motion.div
              className="landing-hero__copy"
              initial={reduceMotion ? false : "hidden"}
              animate="visible"
              variants={{ visible: { transition: { staggerChildren: 0.065, delayChildren: 0.06 } } }}
            >
              <motion.p variants={reveal} transition={{ duration: 0.42 }} className="landing-kicker">
                <BookOpenText aria-hidden="true" /> {heroContent.eyebrow}
              </motion.p>
              <motion.h1
                id="landing-hero-title"
                variants={reveal}
                transition={{ duration: 0.54, ease: [0.22, 1, 0.36, 1] }}
              >
                让抽象知识，<br />
                变成可以亲手操控的推演
              </motion.h1>
              <motion.p variants={reveal} transition={{ duration: 0.46 }} className="landing-hero__description">
                {heroContent.description}
              </motion.p>
              <motion.div variants={reveal} transition={{ duration: 0.42 }} className="landing-hero__actions">
                <Link to="/explore/dijkstra" className="landing-action landing-action--primary">
                  体验交互推演 <ArrowRight aria-hidden="true" />
                </Link>
                <Link
                  to={isAuthenticated ? "/app" : "/app/new"}
                  className="landing-action landing-action--secondary"
                >
                  {isAuthenticated ? "继续上次项目" : "创建新的推演"}
                </Link>
              </motion.div>
            </motion.div>

            <aside className="landing-hero__note" aria-label="本章导读">
              <p>本章导读</p>
              <span />
              <small>以「最短路径问题」为例，观察知识如何在每一步推演中更新认知、收敛答案。</small>
            </aside>
          </div>

          <div className="landing-hero__examples" aria-label="快速案例">
            <span>快速案例</span>
            {heroExamples.map((example, index) => (
              <span key={example}><b>0{index + 1}</b>{example}</span>
            ))}
          </div>

          <section className="landing-hero__demo-plate" id="examples" aria-label="交互案例">
            <Suspense
              fallback={(
                <p className="landing-hero__demo-loading" role="status" aria-live="polite">
                  正在加载交互演示…
                </p>
              )}
            >
              <LazyDijkstraDemo compact />
            </Suspense>
          </section>
        </div>
      </section>

    </>
  );
}
