import { useEffect, useMemo, useRef, useState } from "react";
import { CheckCircle2, ChevronDown, LoaderCircle, RotateCcw, SlidersHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { previewRecomputeProject, recomputeProject, type RecomputeImpact } from "@/services/parameters";
import { streamFromUrl } from "@/services/generate";
import type { SSEConnection } from "@/services/sse";
import type { ArtifactParameter } from "./artifact-model";

function valueForInput(parameter: ArtifactParameter, value: string | boolean) {
  if (parameter.param_type === "boolean") return Boolean(value);
  if (parameter.param_type === "number" || parameter.param_type === "integer") {
    const number = Number(value);
    return parameter.param_type === "integer" ? Math.round(number) : number;
  }
  return value;
}

export function ParameterExperiment({
  projectId,
  parameters,
  onRecomputed,
}: {
  projectId?: string;
  parameters: ArtifactParameter[];
  onRecomputed?: () => void | Promise<void>;
}) {
  const initialValues = useMemo(
    () => Object.fromEntries(parameters.map((parameter) => [parameter.key, parameter.current_value])),
    [parameters],
  );
  const [values, setValues] = useState<Record<string, unknown>>(initialValues);
  const [status, setStatus] = useState<"idle" | "previewing" | "saving" | "recomputing" | "done" | "error">("idle");
  const [message, setMessage] = useState("");
  const [preview, setPreview] = useState<RecomputeImpact | null>(null);
  const [expanded, setExpanded] = useState(false);
  const connectionRef = useRef<SSEConnection | null>(null);

  useEffect(() => setValues(initialValues), [initialValues]);
  useEffect(() => () => connectionRef.current?.close(), []);

  if (parameters.length === 0) return null;

  const changed = parameters.some((parameter) => values[parameter.key] !== initialValues[parameter.key]);

  const changedParams = () => Object.fromEntries(
    parameters
      .filter((parameter) => values[parameter.key] !== initialValues[parameter.key])
      .map((parameter) => [parameter.key, values[parameter.key]]),
  );

  const updateValue = (key: string, value: unknown) => {
    setValues((current) => ({ ...current, [key]: value }));
    setPreview(null);
    setStatus("idle");
    setMessage("");
  };

  const previewChanges = async () => {
    if (!projectId || !changed) return;
    setStatus("previewing");
    setMessage("正在分析参数影响范围…");
    try {
      const impact = await previewRecomputeProject(projectId, changedParams());
      setPreview(impact);
      setStatus("idle");
      setMessage(impact.reason);
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "影响分析失败");
    }
  };

  const applyChanges = async () => {
    if (!projectId || !changed || !preview) return;
    setStatus("saving");
    setMessage("正在保存参数…");
    try {
      const response = await recomputeProject(projectId, changedParams(), preview.impact_token);
      if (response.mode === "local" || !response.stream_url) {
        setStatus("done");
        setMessage("参数已应用，无需重新生成推演帧");
        await onRecomputed?.();
        return;
      }
      setStatus("recomputing");
      setMessage("正在重算推演帧…");
      connectionRef.current?.close();
      connectionRef.current = streamFromUrl(response.stream_url, {
        onProgress: (event) => setMessage(event.message || "正在重算推演帧…"),
        onDone: () => {
          setStatus("done");
          setMessage("参数已应用，推演已更新");
          void onRecomputed?.();
        },
        onError: (event) => {
          setStatus("error");
          setMessage(event.message || "重算失败，请重试");
        },
        reconnectMs: 0,
      });
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "参数保存失败");
    }
  };

  return (
    <section className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--card)]">
      <div className="flex flex-wrap items-center gap-3 px-3 py-2.5">
        <div className="mr-auto min-w-40">
          <p className="flex items-center gap-2 text-xs font-semibold"><SlidersHorizontal size={14} />参数实验</p>
          <p className="mt-1 text-[10px] text-[var(--muted-foreground)]">修改输入后重新计算整段推演</p>
        </div>
        <div className="hidden max-w-[45%] flex-wrap justify-end gap-1.5 md:flex" aria-label="当前参数摘要">
          {parameters.slice(0, 3).map((parameter) => (
            <span key={parameter.key} className="rounded-md bg-[var(--secondary)] px-2 py-1 font-mono text-[9px] text-[var(--muted-foreground)]">
              {parameter.label}：{String(values[parameter.key] ?? "—")}
            </span>
          ))}
          {parameters.length > 3 && <span className="px-1 py-1 text-[9px] text-[var(--muted-foreground)]">+{parameters.length - 3}</span>}
        </div>
        {changed && <span className="rounded-full bg-[color-mix(in_oklch,var(--warning)_14%,var(--card))] px-2 py-1 text-[9px] font-semibold text-[var(--warning)]">有未应用修改</span>}
        <Button
          type="button"
          variant="ghost"
          size="sm"
          aria-expanded={expanded}
          aria-controls="parameter-experiment-controls"
          onClick={() => setExpanded((current) => !current)}
        >
          {expanded ? "收起参数" : `展开参数（${parameters.length}）`}
          <ChevronDown className={`transition-transform ${expanded ? "rotate-180" : ""}`} />
        </Button>
      </div>

      {expanded && (
        <div id="parameter-experiment-controls" className="grid gap-3 border-t border-[var(--border)] bg-[var(--secondary)]/20 p-3 sm:grid-cols-2 xl:grid-cols-4">
          {parameters.map((parameter) => {
            const options = Array.isArray(parameter.constraints.options)
              ? parameter.constraints.options
              : null;
            return (
              <label key={parameter.key} className="min-w-0 text-[10px] text-[var(--muted-foreground)]">
              <span className="mb-1 block">{parameter.label}</span>
              {parameter.param_type === "boolean" ? (
                <input
                  type="checkbox"
                  checked={Boolean(values[parameter.key])}
                  onChange={(event) => updateValue(parameter.key, event.target.checked)}
                  className="h-7 w-7 accent-[var(--interactive)]"
                />
              ) : options ? (
                <select
                  value={String(values[parameter.key] ?? "")}
                  onChange={(event) => updateValue(parameter.key, valueForInput(parameter, event.target.value))}
                  className="h-8 w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-2 text-xs text-[var(--foreground)]"
                >
                  {options.map((option) => <option key={String(option)} value={String(option)}>{String(option)}</option>)}
                </select>
              ) : (
                <input
                  type={parameter.param_type === "number" || parameter.param_type === "integer" ? "number" : "text"}
                  min={typeof parameter.constraints.min === "number" ? parameter.constraints.min : undefined}
                  max={typeof parameter.constraints.max === "number" ? parameter.constraints.max : undefined}
                  step={typeof parameter.constraints.step === "number" ? parameter.constraints.step : undefined}
                  value={String(values[parameter.key] ?? "")}
                  onChange={(event) => updateValue(parameter.key, valueForInput(parameter, event.target.value))}
                  className="h-8 w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-2 text-xs text-[var(--foreground)]"
                />
              )}
              </label>
            );
          })}
          <div className="flex items-end justify-end gap-1 self-end sm:col-span-2 xl:col-span-4">
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label="恢复参数"
            disabled={!changed || status === "previewing" || status === "saving" || status === "recomputing"}
            onClick={() => { setValues(initialValues); setPreview(null); setMessage(""); setStatus("idle"); }}
          >
            <RotateCcw />
          </Button>
          <Button
            size="sm"
            disabled={!projectId || !changed || status === "previewing" || status === "saving" || status === "recomputing"}
            onClick={preview ? applyChanges : previewChanges}
          >
            {(status === "previewing" || status === "saving" || status === "recomputing") && <LoaderCircle className="animate-spin" />}
            {status === "done" && <CheckCircle2 />}
            {preview ? "确认应用并重算" : "预览影响范围"}
          </Button>
          </div>
        </div>
      )}
      {preview && changed && (
        <div className="border-t border-[var(--border)] px-3 py-2 text-[10px] text-[var(--muted-foreground)]" role="region" aria-label="参数影响预览">
          <p className="font-semibold text-[var(--foreground)]">
            {preview.mode === "local"
              ? "仅更新本地渲染"
              : `将重算 ${preview.affected_frame_ids.length} 帧，保留 ${preview.protected_frame_ids.length} 帧`}
          </p>
          {preview.affected_frame_ids.length > 0 && (
            <p className="mt-1 font-mono">影响：{preview.affected_frame_ids.join(" → ")}</p>
          )}
          {(preview.affected_module_ids ?? []).filter((moduleId) => moduleId !== "frames").length > 0 && (
            <p className="mt-1 font-mono text-[var(--warning)]">
              下游产物将标记过期：{(preview.affected_module_ids ?? []).filter((moduleId) => moduleId !== "frames").join("、")}
            </p>
          )}
          {preview.fallback_used && <p className="mt-1 text-[var(--warning)]">依赖信息不足，已安全扩大为全量重算</p>}
        </div>
      )}
      {message && (
        <p className={`border-t border-[var(--border)] px-3 py-2 text-[10px] ${status === "error" ? "text-[var(--error)]" : "text-[var(--muted-foreground)]"}`} role="status">
          {message}
        </p>
      )}
      {!projectId && <p className="border-t border-[var(--border)] px-3 py-2 text-[10px] text-[var(--muted-foreground)]">保存项目后即可进行参数重算。</p>}
    </section>
  );
}
