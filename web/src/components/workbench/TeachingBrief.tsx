import { useState } from "react";
import { ChevronDownIcon, Settings2Icon, SparklesIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from "@/components/ui/field";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupText,
  InputGroupTextarea,
} from "@/components/ui/input-group";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Spinner } from "@/components/ui/spinner";

type TeachingBriefProps = {
  brief: string;
  isPlanning: boolean;
  onBriefChange: (value: string) => void;
  onGenerate: () => void;
};

const stageOptions = [
  { label: "高中信息技术", value: "high-school" },
  { label: "大学计算机基础", value: "university" },
  { label: "算法专题研修", value: "advanced" },
];

function SecondarySettings({ suffix }: { suffix: string }) {
  const [duration, setDuration] = useState(45);

  return (
    <FieldGroup className="gap-4">
      <Field>
        <FieldLabel htmlFor={`course-stage-${suffix}`}>授课阶段</FieldLabel>
        <Select items={stageOptions} defaultValue="university">
          <SelectTrigger id={`course-stage-${suffix}`} className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent alignItemWithTrigger={false} align="start">
            <SelectGroup>
              {stageOptions.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
      </Field>

      <FieldSet>
        <FieldLegend variant="label">学生层级</FieldLegend>
        <ToggleGroup
          aria-label="学生层级"
          defaultValue={["advanced"]}
          variant="outline"
          spacing={0}
          className="w-full"
        >
          <ToggleGroupItem value="starter" className="flex-1">
            入门
          </ToggleGroupItem>
          <ToggleGroupItem value="advanced" className="flex-1">
            进阶
          </ToggleGroupItem>
          <ToggleGroupItem value="expert" className="flex-1">
            高阶
          </ToggleGroupItem>
        </ToggleGroup>
      </FieldSet>

      <Field>
        <div className="flex items-center justify-between gap-3">
          <FieldLabel id={`duration-label-${suffix}`}>课堂时长</FieldLabel>
          <span className="text-sm tabular-nums text-muted-foreground">{duration} 分钟</span>
        </div>
        <Slider
          id={`duration-${suffix}`}
          aria-labelledby={`duration-label-${suffix}`}
          value={[duration]}
          min={15}
          max={90}
          step={5}
          thumbAlignment="center"
          onValueChange={(value) => setDuration((value as number[])[0] ?? 45)}
        />
      </Field>

      <Field orientation="horizontal">
        <FieldLabel htmlFor={`quiz-${suffix}`}>包含练习与随堂测验</FieldLabel>
        <Switch id={`quiz-${suffix}`} defaultChecked />
      </Field>
    </FieldGroup>
  );
}

export function TeachingBrief({
  brief,
  isPlanning,
  onBriefChange,
  onGenerate,
}: TeachingBriefProps) {
  return (
    <section
      aria-labelledby="brief-heading"
      className="flex min-h-0 min-w-0 flex-col overflow-hidden rounded-xl border bg-card"
    >
      <header className="flex items-start justify-between gap-3 border-b px-4 py-4">
        <div className="flex items-start gap-3">
          <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
            1
          </span>
          <div>
            <h2 id="brief-heading" className="font-semibold tracking-tight">
              教学简述
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              用自然语言定义目标与情境
            </p>
          </div>
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
          简报与约束
          <ChevronDownIcon data-icon="inline-end" />
        </CollapsibleTrigger>
        <CollapsibleContent className="flex min-h-0 flex-1 flex-col">
          <form
            className="flex min-h-0 flex-1 flex-col"
            onSubmit={(event) => {
              event.preventDefault();
              onGenerate();
            }}
          >
            <FieldGroup className="min-h-0 flex-1 gap-5 overflow-y-auto p-4">
              <Field>
                <FieldLabel htmlFor="teaching-brief">教学简报</FieldLabel>
                <InputGroup>
                  <InputGroupTextarea
                    id="teaching-brief"
                    rows={8}
                    value={brief}
                    onChange={(event) => onBriefChange(event.target.value)}
                  />
                  <InputGroupAddon align="block-end">
                    <InputGroupText>{brief.length} / 500</InputGroupText>
                  </InputGroupAddon>
                </InputGroup>
                <FieldDescription>
                  写出主题、演示目标与希望学生观察到的变化。
                </FieldDescription>
              </Field>

              <div className="hidden md:block">
                <SecondarySettings suffix="desktop" />
              </div>

              <Sheet>
                <SheetTrigger
                  render={
                    <Button type="button" variant="outline" className="md:hidden" />
                  }
                >
                  <Settings2Icon data-icon="inline-start" />
                  设置课堂约束
                </SheetTrigger>
                <SheetContent side="bottom">
                  <SheetHeader>
                    <SheetTitle>课堂约束</SheetTitle>
                    <SheetDescription>
                      调整学生层级、课堂时长与练习设置。
                    </SheetDescription>
                  </SheetHeader>
                  <div className="px-4 pb-6">
                    <SecondarySettings suffix="mobile" />
                  </div>
                </SheetContent>
              </Sheet>
            </FieldGroup>

            <footer className="border-t p-4">
              <Button type="submit" className="w-full" disabled={isPlanning}>
                {isPlanning ? (
                  <Spinner aria-hidden="true" data-icon="inline-start" />
                ) : (
                  <SparklesIcon data-icon="inline-start" />
                )}
                生成推演计划
              </Button>
            </footer>
          </form>
        </CollapsibleContent>
      </Collapsible>
    </section>
  );
}
