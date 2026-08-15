/**
 * 代码块可视化组件（CodeBlockObject）。
 *
 * 渲染 DSL VisualObject type="code_block" 的代码展示，
 * 支持语法高亮行标记和逐行高亮。
 *
 * 对齐：设计文档 7.1.4 节。
 */

import { memo, useMemo } from "react";
import { cn } from "@/lib/utils";
import type { DSLVisualObject } from "../simulation-model";

export type CodeBlockObjectProps = {
  object: DSLVisualObject;
  /** 高亮行号集合（1-indexed） */
  highlightLines?: Set<number>;
  selectedLine?: number;
  onLineSelect?: (line: number) => void;
  className?: string;
};

/**
 * 简单的关键词语法高亮（无外部依赖）。
 * 支持 Python/C/Java/伪代码 的常见关键词。
 */
function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function highlightSyntaxLine(line: string, language: string): string {
  const KEYWORDS: Record<string, string[]> = {
    python: [
      "def", "class", "return", "if", "elif", "else", "for", "while",
      "import", "from", "as", "try", "except", "raise", "with", "yield",
      "lambda", "pass", "break", "continue", "and", "or", "not", "in", "is",
      "True", "False", "None", "self",
    ],
    c: [
      "int", "float", "double", "char", "void", "return", "if", "else",
      "for", "while", "do", "switch", "case", "break", "continue",
      "struct", "typedef", "sizeof", "NULL", "const", "static",
    ],
    java: [
      "public", "private", "protected", "class", "interface", "extends",
      "implements", "return", "if", "else", "for", "while", "new",
      "try", "catch", "throw", "throws", "static", "final", "void",
      "int", "boolean", "String", "null", "this", "super",
    ],
  };

  const keywords = KEYWORDS[language.toLowerCase()] ?? KEYWORDS.python;
  const escaped = keywords.map((k) => k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const pattern = new RegExp(`\\b(${escaped.join("|")})\\b`, "g");

  const tokenPattern = /(["'`])(?:(?!\1|\\).|\\.)*\1|#.*$|\/\/.*$|\b\d+\.?\d*\b|\b[A-Za-z_]\w*\b/g;

  let output = "";
  let cursor = 0;
  for (const match of line.matchAll(tokenPattern)) {
    const token = match[0];
    const index = match.index ?? 0;
    output += escapeHtml(line.slice(cursor, index));
    if (/^["'`]/.test(token)) {
      output += `<span class="text-success">${escapeHtml(token)}</span>`;
    } else if (token.startsWith("#") || token.startsWith("//")) {
      output += `<span class="text-muted-foreground/70 italic">${escapeHtml(token)}</span>`;
    } else if (/^\d/.test(token)) {
      output += `<span class="text-info">${escapeHtml(token)}</span>`;
    } else if (pattern.test(token)) {
      output += `<span class="text-primary font-medium">${escapeHtml(token)}</span>`;
      pattern.lastIndex = 0;
    } else {
      output += escapeHtml(token);
    }
    cursor = index + token.length;
  }
  output += escapeHtml(line.slice(cursor));
  return output;
}

export const CodeBlockObject = memo(function CodeBlockObject({
  object,
  highlightLines,
  selectedLine,
  onLineSelect,
  className,
}: CodeBlockObjectProps) {
  const code = object.code ?? "";
  const language = object.language ?? "python";
  const lines = useMemo(() => code.split("\n"), [code]);

  const highlightedLines = useMemo(
    () => lines.map((line) => highlightSyntaxLine(line, language)),
    [language, lines],
  );

  if (!code) {
    return (
      <div className={cn("text-xs text-muted-foreground italic", className)}>
        (空代码)
      </div>
    );
  }

  return (
    <div
      className={cn(
        "overflow-hidden rounded-lg border bg-code-bg font-mono text-sm",
        className,
      )}
    >
      {/* 头部 */}
      <div className="flex items-center gap-2 border-b border-white/10 px-3 py-1.5">
        <span className="text-[10px] uppercase tracking-wider text-white/40">
          {language}
        </span>
        {object.label && (
          <span className="text-xs text-white/60">{object.label}</span>
        )}
      </div>

      {/* 代码行 */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <tbody>
            {lines.map((_line, idx) => {
              const lineNum = idx + 1;
              const configuredHighlights = highlightLines ?? new Set(object.highlight_lines ?? []);
              const isHighlighted = configuredHighlights.has(lineNum);

              return (
                <tr
                  key={lineNum}
                  tabIndex={onLineSelect ? 0 : undefined}
                  aria-label={onLineSelect ? `代码第 ${lineNum} 行` : undefined}
                  aria-selected={selectedLine === lineNum || undefined}
                  onClick={(event) => {
                    event.stopPropagation();
                    onLineSelect?.(lineNum);
                  }}
                  onKeyDown={(event) => {
                    if (!onLineSelect || (event.key !== "Enter" && event.key !== " ")) return;
                    event.preventDefault();
                    onLineSelect(lineNum);
                  }}
                  className={cn(
                    "transition-colors",
                    onLineSelect && "cursor-pointer outline-none hover:bg-white/5 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary/70",
                    isHighlighted && "bg-primary/15 ring-1 ring-primary/30",
                    selectedLine === lineNum && "bg-primary/25 ring-1 ring-inset ring-primary/70",
                  )}
                >
                  {/* 行号 */}
                  <td
                    className={cn(
                      "select-none px-3 py-0.5 text-right text-xs text-white/25",
                      isHighlighted && "text-primary/60",
                    )}
                    style={{ width: "3rem" }}
                  >
                    {lineNum}
                  </td>
                  {/* 代码 */}
                  <td
                    className="px-3 py-0.5 text-white/85"
                    dangerouslySetInnerHTML={{
                      __html: highlightedLines[idx] ?? "",
                    }}
                  />
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
});

export default CodeBlockObject;
