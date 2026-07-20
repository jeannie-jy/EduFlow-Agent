import { useCallback, useEffect, useState } from "react";
import { GenerationBorder } from "@/components/effects/GenerationBorder";
import type { GenerationState } from "./AiStatusStrip";
import { PlanSequence } from "./PlanSequence";
import { SimulationPreview } from "./SimulationPreview";

export function WorkbenchPage() {
  const [generation, setGeneration] = useState<GenerationState>("idle");
  const [planStep, setPlanStep] = useState(3);
  const [frame, setFrame] = useState(8);

  const regenerate = useCallback(() => {
    setGeneration("planning");
    setPlanStep(3);
    setFrame(8);
    window.setTimeout(() => setGeneration("ready"), 1600);
  }, []);

  useEffect(() => {
    window.addEventListener("eduflow:regenerate", regenerate);
    return () => window.removeEventListener("eduflow:regenerate", regenerate);
  }, [regenerate]);

  return (
    <main
      data-testid="workbench-page"
      className="flex min-h-[calc(100svh-5rem)] min-w-0 flex-col gap-2.5 lg:h-full lg:min-h-0 lg:overflow-hidden"
    >
      <h1 className="sr-only">教学工作台</h1>
      <PlanSequence generation={generation} activeStep={planStep} onStepChange={setPlanStep} />
      <div data-testid="workbench-regions" className="relative min-h-0 min-w-0 flex-1 lg:overflow-hidden">
        <SimulationPreview
          frame={frame}
          generation={generation}
          onFrameChange={setFrame}
          onRegenerate={regenerate}
        />
        <GenerationBorder generation={generation} />
      </div>
    </main>
  );
}
