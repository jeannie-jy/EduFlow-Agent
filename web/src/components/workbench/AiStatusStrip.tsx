import { BotIcon, RotateCcwIcon } from "lucide-react";
import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Progress, ProgressLabel, ProgressValue } from "@/components/ui/progress";

export type GenerationState = "idle" | "planning" | "ready";

type AiStatusStripProps = {
  generation: GenerationState;
  onRecover: () => void;
};

const statusCopy: Record<GenerationState, { title: string; detail: string; progress: number }> = {
  idle: {
    title: "等待教学简报",
    detail: "调整目标与约束后，生成一条可执行的教学推演路径。",
    progress: 0,
  },
  planning: {
    title: "正在生成推演计划",
    detail: "已读取简报，正在组织“识别知识结构 → 设计教学路径 → 生成交互演示”。",
    progress: 36,
  },
  ready: {
    title: "推演计划已就绪",
    detail: "教学序列与互动预览可以复核。",
    progress: 100,
  },
};

export function AiStatusStrip({ generation, onRecover }: AiStatusStripProps) {
  const status = statusCopy[generation];

  return (
    <Alert role="status" aria-live="polite" className="items-start py-3 pr-28">
      <BotIcon />
      <AlertTitle>{status.title}</AlertTitle>
      <AlertDescription className="flex flex-col gap-2">
        <span>{status.detail}</span>
        <Progress value={status.progress}>
          <ProgressLabel>AI 助教进度</ProgressLabel>
          <ProgressValue />
        </Progress>
      </AlertDescription>
      <AlertAction>
        <Button type="button" variant="ghost" size="sm" onClick={onRecover}>
          <RotateCcwIcon data-icon="inline-start" />
          恢复
        </Button>
      </AlertAction>
    </Alert>
  );
}
