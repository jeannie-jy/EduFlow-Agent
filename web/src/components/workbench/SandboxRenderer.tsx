/**
 * SandboxRenderer — 安全 iframe 沙箱渲染器。
 *
 * 将 LLM 生成的 React JSX 代码字符串在隔离的 iframe 中渲染。
 * 防御等级：全局错误捕获 + Babel JSX 编译 + UMD React + 暴力代码清洗。
 */

import { useMemo } from "react";

export interface SandboxRendererProps {
  code: string;
}

// ============================================================================
// HTML 模板
// ============================================================================

function buildHtml(code: string): string {
  // ═══════════════════════════════════════════════════════
  // 暴力代码清洗
  // ═══════════════════════════════════════════════════════

  let clean = code
    // 剥离 markdown 代码块
    .replace(/```[a-z]*\n?/gi, "")
    .replace(/```/g, "")
    // 剥离所有 import 语句（CDN 环境不支持 ESM）
    .replace(/import\s+.*?;?\n/g, "")
    .replace(/import\s+.*?;?$/gm, "")
    // 剥离 export default
    .replace(/export\s+default\s+/g, "")
    .trim();

  // 如果没有任何内容，给出占位
  if (!clean) {
    clean = "const InteractiveDemo = () => React.createElement('div', null, '暂无代码');";
  }

  // 确保有个叫 InteractiveDemo 的组件（Babel 编译后变量名就是组件）
  if (!clean.includes("InteractiveDemo")) {
    clean = `const InteractiveDemo = () => {\n  return (${clean});\n};`;
  }

  // ═══════════════════════════════════════════════════════
  // HTML 模板
  // ═══════════════════════════════════════════════════════

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />

<!-- 1. 全局错误捕获（必须放在最前面） -->
<script>
  window.onerror = function(msg, url, line, col, error) {
    document.body.innerHTML =
      '<div style="color:#A8463A;padding:20px;font-family:monospace;font-size:14px;line-height:1.6;background:#FFF8E8;border:2px solid #A8463A;border-radius:8px;">' +
      '<h3 style="margin:0 0 12px;font-size:16px;">沙箱渲染崩溃</h3>' +
      '<p style="margin:4px 0"><strong>Error:</strong> ' + msg + '</p>' +
      '<p style="margin:4px 0"><strong>Line:</strong> ' + line + '</p>' +
      (col ? '<p style="margin:4px 0"><strong>Col:</strong> ' + col + '</p>' : '') +
      (error && error.stack ? '<pre style="margin:8px 0 0;font-size:12px;color:#686052;white-space:pre-wrap;">' + error.stack + '</pre>' : '') +
      '</div>';
  };
</script>

<!-- 2. CSS 变量（双主题） -->
<style>
  :root {
    --background: #F3EBD8; --card: #FFF8E8; --secondary: #ECE1C8;
    --foreground: #25231F; --muted-foreground: #686052;
    --interactive: #315E59; --success: #54755B; --error: #A8463A;
    --progress: #B67A2B; --border: #CFC2A5;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --background: #1B1814; --card: #24201B; --secondary: #2E2922;
      --foreground: #EFE4CE; --muted-foreground: #BEB29E;
      --interactive: #70A59A; --success: #7AA184; --error: #E18478;
      --progress: #D6AA5F; --border: #4B4337;
    }
  }
  body {
    margin: 0; padding: 0;
    font-family: 'Inter Variable','Noto Sans SC',system-ui,sans-serif;
    background: var(--background); color: var(--foreground);
  }
  #root { min-height: 200px; }
</style>
</head>
<body>
  <div id="root"></div>

  <!-- 3. CDN 依赖（按顺序加载） -->
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
  <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
  <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>

  <!-- 4. React 18 UMD 挂载 -->
  <script type="text/babel" data-type="module">
    const { useState, useEffect, useRef, useMemo, useCallback } = React;

    ${clean}

    const root = ReactDOM.createRoot(document.getElementById('root'));
    root.render(React.createElement(InteractiveDemo));
  </script>
</body>
</html>`;
}

// ============================================================================
// 组件
// ============================================================================

export function SandboxRenderer({ code }: SandboxRendererProps) {
  const srcDoc = useMemo(() => buildHtml(code), [code]);

  if (!code) {
    return (
      <div className="flex items-center justify-center p-8 text-[var(--muted-foreground)] text-sm">
        暂无演示代码
      </div>
    );
  }

  return (
    <iframe
      srcDoc={srcDoc}
      sandbox="allow-scripts"
      className="w-full min-h-[400px] border-0 rounded-lg bg-[var(--background)]"
      title="交互推演"
    />
  );
}
