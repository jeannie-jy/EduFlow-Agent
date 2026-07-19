import { useState } from "react";
import { WorkspaceGrid } from "@/components/effects/WorkspaceGrid";
import { AiStatusStrip, type GenerationState } from "./AiStatusStrip";
import { PlanSequence } from "./PlanSequence";
import { SimulationPreview } from "./SimulationPreview";
import { TeachingBrief } from "./TeachingBrief";

export function WorkbenchPage() {
  const [generation, setGeneration] = useState<GenerationState>("idle");
  const [brief, setBrief] = useState(
    "演示 Dijkstra 最短路径算法，并解释每一步如何更新距离表",
  );

  return (
    <main className="relative flex min-h-[calc(100svh-7.5rem)] min-w-0 flex-col gap-3">
      <WorkspaceGrid />
      <h1 className="relative sr-only">教学工作台</h1>
      <div
        data-testid="workbench-regions"
        className="relative grid min-h-0 min-w-0 flex-1 grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-[minmax(0,0.8fr)_minmax(0,0.9fr)_minmax(0,1.55fr)]"
      >
        <TeachingBrief
          brief={brief}
          isPlanning={generation === "planning"}
          onBriefChange={setBrief}
          onGenerate={() => setGeneration("planning")}
        />
        <PlanSequence isPlanning={generation === "planning"} />
        <SimulationPreview />
      </div>
      <AiStatusStrip generation={generation} onRecover={() => setGeneration("idle")} />
    </main>
  );
}
