import { BarChart3, BrainCircuit, PlayCircle } from "lucide-react";
import { usePointerParallax } from "./usePointerParallax";

const notes = [
  { className: "scene-note--plan", icon: BrainCircuit, title: "AI 教学规划", copy: "自动拆解知识路径" },
  { className: "scene-note--play", icon: PlayCircle, title: "交互式推演", copy: "逐帧探索关键变化" },
  { className: "scene-note--track", icon: BarChart3, title: "学习轨迹", copy: "看见每一次理解" },
];

export function BookHeroScene({ compact = false }: { compact?: boolean }) {
  const { offset, onPointerMove, onPointerLeave } = usePointerParallax(compact ? 4 : 8);

  return (
    <figure
      className={`book-scene${compact ? " book-scene--compact" : ""}`}
      onMouseMove={onPointerMove}
      onMouseLeave={onPointerLeave}
      style={{ "--parallax-x": `${offset.x}px`, "--parallax-y": `${offset.y}px` } as React.CSSProperties}
    >
      <div className="book-scene__halo" aria-hidden="true" />
      <div className="book-scene__art">
        <img
          className="book-scene__image"
          src="/brand/eduflow-book-hero.png"
          alt="一本展开的智慧书籍，知识节点围绕播放符号流动"
        />
        <img className="book-scene__page book-scene__page--left" src="/brand/eduflow-book-hero.png" alt="" />
        <img className="book-scene__page book-scene__page--right" src="/brand/eduflow-book-hero.png" alt="" />
      </div>
      {!compact &&
        notes.map(({ className, icon: Icon, title, copy }) => (
          <figcaption className={`scene-note ${className}`} key={title}>
            <span className="scene-note__icon"><Icon size={18} strokeWidth={2.1} /></span>
            <span><strong>{title}</strong><small>{copy}</small></span>
          </figcaption>
        ))}
    </figure>
  );
}
