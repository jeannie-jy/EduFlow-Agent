/**
 * CodeSandbox — 代码实操沙箱组件。
 *
 * 展示算法代码、测试用例和可调参数。
 */

import { useEffect, useMemo, useState } from "react";
import { Code2, CheckCircle2, Copy, ChevronDown, ChevronUp, Package, FileText, Settings, BookOpen, RotateCcw, ShieldCheck, Clock3 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

// ============================================================================
// 类型
// ============================================================================

export interface SandboxTestCase {
  name: string;
  input: Record<string, unknown>;
  expected_output: Record<string, unknown>;
  description?: string;
}

export interface SandboxEditableParam {
  key: string;
  label: string;
  type: string;
  default: unknown;
  description?: string;
}

export interface SandboxData {
  language: string;
  starter_code: string;
  full_solution: string;
  test_cases: SandboxTestCase[];
  editable_params?: SandboxEditableParam[];
  learning_notes?: string;
  time_complexity?: string;
  space_complexity?: string;
}

export interface CodeSandboxProps {
  data: SandboxData;
}

// ============================================================================
// 组件
// ============================================================================

const LANGUAGE_LABELS: Record<string, string> = {
  python: "Python", javascript: "JavaScript", java: "Java", cpp: "C++",
};

export function CodeSandbox({ data }: CodeSandboxProps) {
  const [showSolution, setShowSolution] = useState(false);
  const [copied, setCopied] = useState(false);
  const [code, setCode] = useState(data.starter_code);
  const [paramValues, setParamValues] = useState<Record<string, unknown>>(() =>
    Object.fromEntries((data.editable_params ?? []).map((parameter) => [parameter.key, parameter.default])),
  );
  const [checkMessage, setCheckMessage] = useState("");

  useEffect(() => {
    setCode(data.starter_code);
    setCheckMessage("");
    setParamValues(Object.fromEntries((data.editable_params ?? []).map((parameter) => [parameter.key, parameter.default])));
  }, [data.editable_params, data.starter_code]);

  const changed = code !== data.starter_code;
  const remainingPlaceholders = useMemo(
    () => (code.match(/TODO|\bpass\b|\.\.\./g) ?? []).length,
    [code],
  );

  if (!data.starter_code && !data.full_solution) {
    return <div className="p-8 text-center text-[var(--muted-foreground)]">暂无代码数据</div>;
  }

  const handleCopy = async (code: string) => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Code2 size={20} className="text-[var(--interactive)]" />
          <h3 className="text-lg font-bold text-[var(--foreground)]">
            {LANGUAGE_LABELS[data.language] ?? data.language} 代码
          </h3>
        </div>
        <div className="flex items-center gap-2">
          {data.time_complexity && (
            <Badge variant="outline" className="gap-1 text-xs"><Clock3 size={12} /> {data.time_complexity}</Badge>
          )}
          {data.space_complexity && (
            <Badge variant="outline" className="text-xs gap-1"><Package size={12} /> {data.space_complexity}</Badge>
          )}
        </div>
      </div>

      {/* Starter Code */}
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_18rem]">
        <div>
        <div className="flex items-center justify-between mb-1">
          <p className="flex items-center gap-1 text-xs font-medium text-gray-500"><FileText size={12} /> 练习代码</p>
          <div className="flex items-center gap-1">
          <Button variant="ghost" size="sm" className="h-6 gap-1 text-xs" disabled={!changed} onClick={() => { setCode(data.starter_code); setCheckMessage(""); }}>
            <RotateCcw size={12} /> 重置
          </Button>
          <Button variant="ghost" size="sm" className="h-6 gap-1 text-xs" onClick={() => handleCopy(code)}>
            <Copy size={12} /> {copied ? "已复制" : "复制"}
          </Button>
          </div>
        </div>
        <textarea
          aria-label="练习代码编辑器"
          value={code}
          onChange={(event) => { setCode(event.target.value); setCheckMessage(""); }}
          spellCheck={false}
          className="min-h-80 w-full resize-y rounded-lg border border-white/10 bg-gray-950 p-4 font-mono text-xs leading-6 text-[var(--success)] outline-none focus:border-[var(--interactive)]"
        />
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            onClick={() => setCheckMessage(
              remainingPlaceholders > 0
                ? `还有 ${remainingPlaceholders} 处待完成内容，请继续补充。`
                : changed
                  ? "静态检查通过：占位内容已清除。请复制到本地运行环境验证测试结果。"
                  : "代码尚未修改。请完成练习后再检查。",
            )}
          >
            <ShieldCheck />检查练习
          </Button>
          <span className="text-[10px] text-[var(--muted-foreground)]">安全说明：这里进行编辑和静态检查，不在浏览器中执行任意代码。</span>
        </div>
        {checkMessage && <p className="mt-2 text-xs text-[var(--muted-foreground)]" role="status">{checkMessage}</p>}
        </div>

        <aside className="space-y-3">
          <div className="rounded-lg border border-[var(--border)] bg-[var(--secondary)]/35 p-3">
            <p className="text-xs font-semibold">练习进度</p>
            <dl className="mt-2 space-y-2 text-xs">
              <div className="flex justify-between"><dt className="text-[var(--muted-foreground)]">代码状态</dt><dd>{changed ? "已修改" : "未开始"}</dd></div>
              <div className="flex justify-between"><dt className="text-[var(--muted-foreground)]">待完成处</dt><dd className="font-mono">{remainingPlaceholders}</dd></div>
              <div className="flex justify-between"><dt className="text-[var(--muted-foreground)]">测试用例</dt><dd className="font-mono">{data.test_cases.length}</dd></div>
            </dl>
          </div>

          {data.editable_params && data.editable_params.length > 0 && (
            <div className="rounded-lg border border-[var(--border)] p-3">
              <p className="flex items-center gap-1 text-xs font-semibold"><Settings size={12} /> 测试参数</p>
              <div className="mt-3 space-y-3">
                {data.editable_params.map((parameter) => (
                  <label key={parameter.key} className="block text-[10px] text-[var(--muted-foreground)]">
                    <span className="mb-1 block">{parameter.label}</span>
                    <input
                      type={parameter.type === "number" ? "number" : "text"}
                      value={typeof paramValues[parameter.key] === "object" ? JSON.stringify(paramValues[parameter.key]) : String(paramValues[parameter.key] ?? "")}
                      onChange={(event) => setParamValues((current) => ({
                        ...current,
                        [parameter.key]: parameter.type === "number" ? Number(event.target.value) : event.target.value,
                      }))}
                      className="h-8 w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-2 text-xs text-[var(--foreground)]"
                    />
                    {parameter.description && <span className="mt-1 block leading-4">{parameter.description}</span>}
                  </label>
                ))}
              </div>
            </div>
          )}
        </aside>
      </div>

      {/* Full Solution (toggle) */}
      <div>
        <button
          onClick={() => setShowSolution(!showSolution)}
          className="flex items-center gap-1 text-xs font-medium text-[var(--interactive)] hover:underline"
        >
          {showSolution ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          {showSolution ? "隐藏" : "查看"}完整解答
        </button>
        {showSolution && (
          <pre className="mt-2 overflow-x-auto rounded-lg bg-gray-900 p-4 text-xs text-[var(--success)] dark:bg-gray-950">
            <code>{data.full_solution}</code>
          </pre>
        )}
      </div>

      {/* Test Cases */}
      {data.test_cases.length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-500 mb-2">
            <CheckCircle2 size={14} className="inline mr-1" />
            测试用例 ({data.test_cases.length})
          </p>
          <div className="flex flex-col gap-2">
            {data.test_cases.map((tc, i) => (
              <div key={i} className="rounded-lg border border-gray-200 p-3 dark:border-gray-700">
                <p className="text-sm font-semibold text-[var(--foreground)]">{tc.name}</p>
                {tc.description && (
                  <p className="text-xs text-[var(--muted-foreground)] mt-0.5">{tc.description}</p>
                )}
                <div className="mt-2 grid gap-1 text-xs">
                  <div className="flex gap-2">
                    <span className="text-[var(--muted-foreground)]">输入:</span>
                    <code className="text-[var(--interactive)]">{JSON.stringify(tc.input)}</code>
                  </div>
                  <div className="flex gap-2">
                    <span className="text-[var(--muted-foreground)]">期望:</span>
                    <code className="text-[var(--success)]">{JSON.stringify(tc.expected_output)}</code>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Learning Notes */}
      {data.learning_notes && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 dark:border-blue-800 dark:bg-blue-950">
          <p className="flex items-center gap-1 text-sm font-semibold text-[var(--interactive)] mb-1"><BookOpen size={14} /> 学习笔记</p>
          <p className="text-sm text-[var(--interactive)]">{data.learning_notes}</p>
        </div>
      )}
    </div>
  );
}
