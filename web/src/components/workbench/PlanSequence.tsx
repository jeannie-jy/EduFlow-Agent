import {
  BrainCircuitIcon,
  ChevronDownIcon,
  MonitorPlayIcon,
  RouteIcon,
  ShieldCheckIcon,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemGroup,
  ItemMedia,
  ItemTitle,
} from "@/components/ui/item";

type PlanSequenceProps = {
  isPlanning: boolean;
};

const planSteps = [
  {
    title: "识别知识结构",
    description: "提取最短路径、松弛与已确定节点",
    duration: "4 分钟",
    icon: BrainCircuitIcon,
  },
  {
    title: "设计教学路径",
    description: "从直觉问题过渡到距离表更新规则",
    duration: "8 分钟",
    icon: RouteIcon,
  },
  {
    title: "生成交互演示",
    description: "逐步展示选点、松弛与前驱变化",
    duration: "18 分钟",
    icon: MonitorPlayIcon,
  },
  {
    title: "复核讲解与状态",
    description: "核对算法结论并设计课堂追问",
    duration: "5 分钟",
    icon: ShieldCheckIcon,
  },
];

export function PlanSequence({ isPlanning }: PlanSequenceProps) {
  return (
    <section
      aria-labelledby="plan-heading"
      className="flex min-h-0 min-w-0 flex-col overflow-hidden rounded-xl border bg-card"
    >
      <header className="flex items-start gap-3 border-b px-4 py-4">
        <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
          2
        </span>
        <div>
          <h2 id="plan-heading" className="font-semibold tracking-tight">
            教学规划
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            AI 组织可执行的教学流程
          </p>
        </div>
      </header>

      <Collapsible defaultOpen className="flex min-h-0 flex-1 flex-col">
        <CollapsibleTrigger
          render={
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="mx-3 mt-3 flex justify-between"
            />
          }
        >
          推演序列 · {planSteps.length} 步
          <ChevronDownIcon data-icon="inline-end" />
        </CollapsibleTrigger>
        <CollapsibleContent className="min-h-0 flex-1">
          <div className="h-full max-h-[34rem] overflow-y-auto xl:max-h-none">
            <div className="p-4">
              <ItemGroup className="relative gap-3 before:absolute before:top-7 before:bottom-7 before:left-7 before:w-px before:bg-border">
                {planSteps.map((step, index) => {
                  const Icon = step.icon;
                  const active = isPlanning && index === 2;

                  return (
                    <Item
                      key={step.title}
                      role="listitem"
                      variant={active ? "muted" : "outline"}
                      aria-current={active ? "step" : undefined}
                      className="relative bg-card"
                    >
                      <ItemMedia>
                        <span className="flex size-8 items-center justify-center rounded-full border bg-background text-primary">
                          <Icon className="size-4" aria-hidden="true" />
                        </span>
                      </ItemMedia>
                      <ItemContent>
                        <ItemTitle>{step.title}</ItemTitle>
                        <ItemDescription>{step.description}</ItemDescription>
                      </ItemContent>
                      <ItemActions>
                        {active ? (
                          <Badge>生成中</Badge>
                        ) : (
                          <Badge variant="secondary">{step.duration}</Badge>
                        )}
                      </ItemActions>
                    </Item>
                  );
                })}
              </ItemGroup>
            </div>
          </div>
        </CollapsibleContent>
      </Collapsible>
    </section>
  );
}
