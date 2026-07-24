import { Link } from "react-router-dom";
import { DijkstraDemo } from "@/features/demo/DijkstraDemo";
import { SiteHeader } from "@/features/landing/components/SiteHeader";

export function DijkstraExplorePage() {
  return (
    <div className="dijkstra-explore">
      <SiteHeader />
      <main className="dijkstra-explore__main">
        <header className="dijkstra-explore__intro">
          <p className="dijkstra-explore__eyebrow">公开交互案例</p>
          <h1>Dijkstra 最短路径交互推演</h1>
          <p className="dijkstra-explore__lede">逐帧观察选点、松弛和距离表变化，再修改一条边权重新计算路径。</p>
        </header>

        <DijkstraDemo autoFocusControls />

        <section className="dijkstra-explore__what-you-saw" aria-labelledby="what-you-saw">
          <p className="dijkstra-explore__eyebrow">案例笔记</p>
          <h2 id="what-you-saw">你刚刚体验了什么</h2>
          <ul>
            <li>教学计划与逐帧讲解同步</li>
            <li>参数变化驱动状态重算</li>
            <li>同一内容可以继续编辑和导出</li>
          </ul>
          <Link to="/app/new?template=dijkstra" className="dijkstra-explore__create-link">
            基于这个案例创建
          </Link>
        </section>
      </main>
    </div>
  );
}
