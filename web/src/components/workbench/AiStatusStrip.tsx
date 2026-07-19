import { CheckCircle2Icon, RotateCwIcon } from "lucide-react";

export type GenerationState = "idle" | "planning" | "ready";

export function AiStatusStrip({ generation }: { generation: GenerationState }) {
  const isPlanning = generation === "planning";
  const isReady = generation === "ready";

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex min-w-39 items-center justify-end gap-2 border-l pl-5 text-sm font-medium"
    >
      {isPlanning ? (
        <span className="micro-loader flex items-end gap-1" aria-hidden="true">
          <span className="size-1.5 rounded-full bg-primary" />
          <span className="size-1.5 rounded-full bg-primary" />
          <span className="size-1.5 rounded-full bg-primary" />
        </span>
      ) : isReady ? (
        <CheckCircle2Icon className="size-4 text-success" aria-hidden="true" />
      ) : (
        <RotateCwIcon className="size-4 text-muted-foreground" aria-hidden="true" />
      )}
      <span>
        {isPlanning ? "正在生成第 3 帧" : isReady ? "推演已更新" : "推演已就绪"}
      </span>
    </div>
  );
}
