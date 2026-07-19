import type { GenerationState } from "@/components/workbench/AiStatusStrip";
import { BorderBeam } from "@/components/ui/border-beam";

type GenerationBorderProps = {
  generation: GenerationState;
};

export function GenerationBorder({ generation }: GenerationBorderProps) {
  if (generation !== "planning") {
    return null;
  }

  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 rounded-[inherit]">
      <div className="absolute inset-0 rounded-[inherit] border border-primary/45" />
      <BorderBeam
        className="motion-reduce:hidden"
        borderWidth={2}
        colorFrom="var(--primary)"
        colorTo="var(--ring)"
        duration={6}
        size={72}
      />
    </div>
  );
}
