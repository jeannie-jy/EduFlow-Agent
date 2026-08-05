/**
 * CodeSandbox — 代码实操沙箱组件。
 *
 * 展示算法代码、测试用例和可调参数。
 */

import { useState } from "react";
import { Code2, CheckCircle2, Copy, ChevronDown, ChevronUp, Package, FileText, Settings, BookOpen } from "lucide-react";
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
            <Badge variant="outline" className="text-xs">⏱ {data.time_complexity}</Badge>
          )}
          {data.space_complexity && (
            <Badge variant="outline" className="text-xs gap-1"><Package size={12} /> {data.space_complexity}</Badge>
          )}
        </div>
      </div>

      {/* Starter Code */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <p className="flex items-center gap-1 text-xs font-medium text-gray-500"><FileText size={12} /> 初始代码</p>
          <Button variant="ghost" size="sm" className="h-6 gap-1 text-xs" onClick={() => handleCopy(data.starter_code)}>
            <Copy size={12} /> {copied ? "已复制" : "复制"}
          </Button>
        </div>
        <pre className="overflow-x-auto rounded-lg bg-gray-900 p-4 text-xs text-[var(--success)] dark:bg-gray-950">
          <code>{data.starter_code}</code>
        </pre>
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

      {/* Editable Params */}
      {data.editable_params && data.editable_params.length > 0 && (
        <div>
          <p className="flex items-center gap-1 text-xs font-medium text-gray-500 mb-2"><Settings size={12} /> 可调参数</p>
          <div className="flex flex-wrap gap-2">
            {data.editable_params.map((p) => (
              <Badge key={p.key} variant="outline" className="text-xs">
                {p.label}: {JSON.stringify(p.default)}
              </Badge>
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
