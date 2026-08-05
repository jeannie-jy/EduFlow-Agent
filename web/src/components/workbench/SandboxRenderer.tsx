/**
 * SandboxRenderer — 安全 iframe 沙箱渲染器。
 *
 * 将 LLM 生成的 React JSX 代码字符串在隔离的 iframe 中渲染。
 *
 * 架构（v0.8.1）：
 * - JSX 编译在「宿主侧」完成（Babel standalone + runtime: classic → 纯 React.createElement），
 *   iframe 只接收编译后的 JS，不再注入 Babel 运行时 —— 避免 Babel automatic runtime
 *   在 iframe 内输出 import 语句导致的静默失败
 * - React/ReactDOM UMD 从 node_modules 本地注入（unpkg CDN 在部分网络不可达，
 *   脚本加载失败不触发 window.onerror，会造成静默空白）
 * - Tailwind 仍走 CDN（缺失时只影响样式、不影响渲染）
 * - 转译错误在宿主侧捕获并显示友好错误面板，运行时错误由 iframe 内 window.onerror 捕获
 */

import { useEffect, useMemo, useState } from "react";

// 本地 React 18 UMD（react 包的 exports 未暴露 ./umd/*，用相对路径绕过）
import reactUMD from "../../../node_modules/react/umd/react.production.min.js?raw";
import reactDOMUMD from "../../../node_modules/react-dom/umd/react-dom.production.min.js?raw";

export interface SandboxRendererProps {
  code: string;
}

// ============================================================================
// 代码清洗（对齐沙箱约束：无 import / 无 export / 无 markdown 包裹）
// ============================================================================

function cleanCode(code: string): string {
  let clean = code
    // 剥离 markdown 代码块
    .replace(/```[a-z]*\n?/gi, "")
    .replace(/```/g, "")
    // 剥离所有 import 语句（沙箱环境不支持 ESM）
    .replace(/import\s+.*?;?\n/g, "")
    .replace(/import\s+.*?;?$/gm, "")
    // 剥离 export default
    .replace(/export\s+default\s+/g, "")
    .trim();

  // 如果没有任何内容，给出占位
  if (!clean) {
    clean = "const InteractiveDemo = () => React.createElement('div', null, '暂无代码');";
  }

  // 确保有个叫 InteractiveDemo 的组件（编译后变量名就是组件）
  if (!clean.includes("InteractiveDemo")) {
    clean = "const InteractiveDemo = () => {\n  return (" + clean + ");\n};";
  }

  return clean;
}

// ============================================================================
// HTML 模板
// ============================================================================

function buildHtml(compiledJs: string): string {
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

<!-- 2. CSS 变量（双主题）
     注意：iframe 隔离文档无法继承宿主 CSS 变量，这里的色值与 globals.css 的
     --background/--card/--interactive/--success/--error 等语义变量同步维护，
     修改 globals.css 调色板时需同步更新此处。 -->
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

  <!-- 3. 运行时依赖：React UMD 本地注入（不走 CDN，见文件头注释） -->
  <script>${reactUMD}</script>
  <script>${reactDOMUMD}</script>

  <!-- Tailwind Play CDN：仅提供样式，加载失败不影响渲染 -->
  <script src="https://cdn.tailwindcss.com"></script>

  <!-- 4. 编译后的组件 JS（宿主侧 Babel 已转译为 React.createElement） -->
  <script>
    ${compiledJs}

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
  const [compiled, setCompiled] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Babel standalone 体积较大（~2.6MB），动态加载拆为独立 chunk，仅渲染时下载
  useEffect(() => {
    let cancelled = false;
    setCompiled(null);
    setError(null);

    if (!code) return;

    import("@babel/standalone")
      .then((mod) => {
        if (cancelled) return;
        try {
          const result = mod.default.transform(cleanCode(code), {
            presets: [["react", { runtime: "classic" }]],
            filename: "interactive-demo.jsx",
          });
          if (!cancelled) setCompiled(result.code ?? "");
        } catch (err) {
          if (!cancelled) {
            setError(err instanceof Error ? err.message : String(err));
          }
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [code]);

  const srcDoc = useMemo(
    () => (compiled === null ? "" : buildHtml(compiled)),
    [compiled],
  );

  if (!code) {
    return (
      <div className="flex items-center justify-center p-8 text-sm text-[var(--muted-foreground)]">
        暂无演示代码
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-2 rounded-lg border border-[var(--error)] p-4">
        <p className="text-sm font-medium text-[var(--error)]">演示代码编译失败</p>
        <pre className="max-h-48 overflow-auto rounded bg-[var(--secondary)] p-3 font-mono text-xs text-[var(--muted-foreground)]">
          {error}
        </pre>
      </div>
    );
  }

  if (compiled === null) {
    return (
      <div className="flex items-center justify-center p-8 text-sm text-[var(--muted-foreground)]">
        正在加载交互推演运行环境...
      </div>
    );
  }

  return (
    <iframe
      srcDoc={srcDoc}
      sandbox="allow-scripts"
      className="w-full min-h-[400px] rounded-lg border-0 bg-[var(--background)]"
      title="交互推演"
    />
  );
}
