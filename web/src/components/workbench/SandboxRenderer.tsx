/**
 * SandboxRenderer — 安全 iframe 沙箱渲染器。
 *
 * 将 LLM 生成的 React JSX 代码字符串在隔离的 iframe 中渲染。
 * 防御：Babel 编译 JSX + UMD React（无 import）+ 剥离 markdown 包裹。
 */

import { useMemo } from "react";

export interface SandboxRendererProps {
  code: string;
}

// ============================================================================
// HTML 模板
// ============================================================================

function buildHtml(code: string): string {
  // 剥离 LLM 可能残留的 markdown 代码块包裹
  const cleanCode = code
    .replace(/```[a-z]*\n?/gi, "")
    .replace(/```/g, "")
    .trim();

  // 如果代码以 "const InteractiveDemo" 开头，确保最后调用 render
  const renderCall = `
const __root = ReactDOM.createRoot(document.getElementById('root'));
__root.render(React.createElement(InteractiveDemo));
`;

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<script src="https://cdn.tailwindcss.com"></script>
<style>
  :root {
    --background: #F3EBD8;
    --card: #FFF8E8;
    --secondary: #ECE1C8;
    --foreground: #25231F;
    --muted-foreground: #686052;
    --interactive: #315E59;
    --success: #54755B;
    --error: #A8463A;
    --progress: #B67A2B;
    --border: #CFC2A5;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --background: #1B1814;
      --card: #24201B;
      --secondary: #2E2922;
      --foreground: #EFE4CE;
      --muted-foreground: #BEB29E;
      --interactive: #70A59A;
      --success: #7AA184;
      --error: #E18478;
      --progress: #D6AA5F;
      --border: #4B4337;
    }
  }
  body {
    margin: 0;
    padding: 0;
    font-family: 'Inter Variable', 'Noto Sans SC', system-ui, sans-serif;
    background: var(--background);
    color: var(--foreground);
  }
</style>
</head>
<body>
  <div id="root"></div>
  <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
  <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
  <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
  <script>
    // 全局 Hook 别名 — LLM 生成的代码可直接使用
    window.useState = React.useState;
    window.useEffect = React.useEffect;
    window.useRef = React.useRef;
    window.useCallback = React.useCallback;
    window.useMemo = React.useMemo;
  </script>
  <script type="text/babel" data-type="module">
    ${cleanCode}
    ${renderCall}
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
      title="交互演示"
    />
  );
}
