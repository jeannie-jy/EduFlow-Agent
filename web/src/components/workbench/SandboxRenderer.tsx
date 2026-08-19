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
 * - Tailwind 样式在宿主侧按产物代码实际使用的 class 本地编译，不依赖 CDN
 * - 转译错误在宿主侧捕获并显示友好错误面板，运行时错误由 iframe 内 window.onerror 捕获
 */

import { useEffect, useMemo, useState } from "react";
import tailwindPreflight from "../../../node_modules/tailwindcss/preflight.css?raw";

// 本地 React 18 UMD（react 包的 exports 未暴露 ./umd/*，用相对路径绕过）
import reactUMD from "../../../node_modules/react/umd/react.production.min.js?raw";
import reactDOMUMD from "../../../node_modules/react-dom/umd/react-dom.production.min.js?raw";

export interface SandboxRendererProps {
  code: string;
  experienceKind?: "network" | "hierarchy" | "sequence" | "collection" | "state" | "code" | "concept";
}

const SANDBOX_TAILWIND_THEME = `
@theme {
  --spacing: 0.25rem;
  --radius-sm: 0.25rem;
  --radius-md: 0.375rem;
  --radius-lg: 0.5rem;
  --radius-xl: 0.75rem;
  --radius-2xl: 1rem;
  --text-xs: 0.75rem;
  --text-sm: 0.875rem;
  --text-base: 1rem;
  --text-lg: 1.125rem;
  --text-xl: 1.25rem;
  --text-2xl: 1.5rem;
  --text-3xl: 1.875rem;
  --text-4xl: 2.25rem;
  --font-mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  --breakpoint-sm: 40rem;
  --breakpoint-md: 48rem;
  --breakpoint-lg: 64rem;
  --color-white: #fff;
  --color-black: #000;
}
@tailwind utilities;
`;

const LEGACY_CONTROL_POLISH = `
  #root button:not(.eduflow-demo__button) {
    min-height: 42px;
    border: 1px solid var(--border);
    border-radius: 10px;
    background: color-mix(in srgb, var(--card) 96%, var(--secondary));
    color: var(--foreground);
    padding: 8px 15px;
    font-weight: 650;
    line-height: 1.2;
    box-shadow: 0 1px 0 color-mix(in srgb, #fff 45%, transparent);
    transition: transform 150ms ease, border-color 150ms ease, background 150ms ease, color 150ms ease, box-shadow 150ms ease;
  }
  #root button:not(.eduflow-demo__button):hover:not(:disabled) {
    border-color: color-mix(in srgb, var(--interactive) 58%, var(--border));
    background: var(--secondary);
    transform: translateY(-1px);
  }
  #root button:not(.eduflow-demo__button):active:not(:disabled) { transform: translateY(0) scale(.98); }
  #root button:not(.eduflow-demo__button):focus-visible {
    outline: 3px solid color-mix(in srgb, var(--interactive) 24%, transparent);
    outline-offset: 2px;
  }
  #root button[data-sandbox-action="primary"] {
    border-color: var(--interactive);
    background: var(--interactive);
    color: var(--card);
    box-shadow: 0 5px 14px color-mix(in srgb, var(--interactive) 20%, transparent);
  }
  #root button[data-sandbox-action="primary"]:hover:not(:disabled) {
    background: color-mix(in srgb, var(--interactive) 88%, var(--foreground));
    color: var(--card);
  }
  #root button[data-sandbox-action="reset"] {
    border-color: transparent;
    background: transparent;
    color: var(--muted-foreground);
    box-shadow: none;
  }
  #root button[data-sandbox-action="reset"]:hover:not(:disabled) { background: var(--secondary); color: var(--foreground); }
  #root input[type="range"] {
    height: 6px;
    border-radius: 999px;
    accent-color: var(--interactive);
    cursor: pointer;
  }
  #root input[type="range"]::-webkit-slider-thumb {
    width: 20px;
    height: 20px;
    border: 3px solid var(--card);
    border-radius: 50%;
    background: var(--interactive);
    box-shadow: 0 0 0 1px var(--interactive), 0 3px 8px color-mix(in srgb, var(--foreground) 18%, transparent);
  }
  #root [data-sandbox-controls="true"] {
    border-color: color-mix(in srgb, var(--interactive) 18%, var(--border)) !important;
    background: color-mix(in srgb, var(--card) 94%, var(--background)) !important;
    box-shadow: 0 10px 28px color-mix(in srgb, var(--foreground) 6%, transparent);
  }
`;

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

function extractTailwindCandidates(code: string): string[] {
  const candidates = new Set<string>();
  const classPattern = /className\s*=\s*(?:["']([^"']*)["']|{\s*`([^`]*)`\s*})/g;

  for (const match of code.matchAll(classPattern)) {
    const classList = (match[1] ?? match[2] ?? "").replace(/\$\{[^}]*}/g, " ");
    classList.split(/\s+/).filter(Boolean).forEach((candidate) => candidates.add(candidate));
  }

  return [...candidates];
}

async function compileTailwindCss(code: string): Promise<string> {
  const { compile } = await import("tailwindcss");
  const compiler = await compile(SANDBOX_TAILWIND_THEME);
  return compiler.build(extractTailwindCandidates(code));
}

// ============================================================================
// HTML 模板
// ============================================================================

function buildHtml(compiledJs: string, utilityCss: string, experienceKind: string): string {
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />

<!-- 1. 全局错误捕获（必须放在最前面） -->
<script>
  window.onerror = function(msg, url, line, col, error) {
    document.body.innerHTML =
      '<div style="color:#25231F;padding:24px;font-family:system-ui,sans-serif;font-size:14px;line-height:1.7;background:#FFF8E8;border:1px solid #CFC2A5;border-radius:14px;">' +
      '<h3 style="margin:0 0 8px;font-size:17px;">互动内容暂时无法展示</h3>' +
      '<p style="margin:0;color:#686052;">这份互动内容的展示格式不完整，请返回成果页重新生成。</p>' +
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
    margin: 0; padding: 16px;
    font-family: 'Inter Variable','Noto Sans SC',system-ui,sans-serif;
    background: var(--background); color: var(--foreground);
  }
  #root { min-height: 200px; }
  *, *::before, *::after { box-sizing: border-box; }
  button, input, select { font: inherit; }
  button { cursor: pointer; }
  button:disabled { cursor: not-allowed; opacity: .42; }

  .eduflow-demo { display:grid; gap:16px; border:1px solid var(--border); background:color-mix(in srgb,var(--card) 94%,var(--background)); padding:clamp(16px,2vw,28px); }
  .eduflow-demo__header,.eduflow-demo__explanation,.eduflow-demo__timeline-header { display:flex; align-items:center; justify-content:space-between; gap:16px; }
  .eduflow-demo__header h2,.eduflow-demo__status h3 { margin:4px 0 0; font-family:Georgia,'Noto Serif SC',serif; }
  .eduflow-demo__header h2 { font-size:clamp(20px,2vw,28px); }
  .eduflow-demo__eyebrow { margin:0; color:var(--error); font-family:Georgia,'Noto Serif SC',serif; font-size:11px; font-weight:700; letter-spacing:.08em; text-transform:uppercase; }
  .eduflow-demo__mode { color:var(--interactive); font-size:13px; font-weight:700; }
  .eduflow-demo__stage { display:grid; grid-template-columns:minmax(0,1.8fr) minmax(240px,.85fr); gap:16px; min-height:410px; }
  .eduflow-demo__visual,.eduflow-demo__status { border:1px solid var(--border); background:var(--card); }
  .eduflow-demo__visual { position:relative; overflow:auto; padding:20px; background-color:var(--background); background-image:radial-gradient(circle,color-mix(in srgb,var(--border) 55%,transparent) .8px,transparent .9px); background-size:20px 20px; }
  .eduflow-demo__status { padding:16px; overflow:auto; }
  .eduflow-demo__status table { width:100%; margin-top:14px; border-collapse:collapse; font-size:13px; }
  .eduflow-demo__status th,.eduflow-demo__status td { border-top:1px solid var(--border); padding:9px 5px; text-align:left; }
  .eduflow-demo__status th { font-weight:700; }
  .eduflow-demo__explanation,.eduflow-demo__timeline { border-top:1px solid var(--border); padding-top:16px; }
  .eduflow-demo__narration { min-width:0; flex:1; }
  .eduflow-demo__narration>p:last-child { margin:6px 0 0; line-height:1.6; }
  .eduflow-demo__controls { display:flex; flex-wrap:wrap; align-items:center; justify-content:flex-end; gap:8px; }
  .eduflow-demo__button { min-height:42px; border:1px solid var(--border); border-radius:10px; background:var(--card); color:var(--foreground); padding:9px 16px; font-weight:650; transition:transform 160ms ease,background 160ms ease,border-color 160ms ease; }
  .eduflow-demo__button:hover { border-color:var(--interactive); background:var(--secondary); }
  .eduflow-demo__button:active { transform:scale(.97); }
  .eduflow-demo__button.is-primary { border-color:var(--error); background:var(--error); color:#fff; }
  .eduflow-demo__button.is-icon { min-width:42px; padding-inline:12px; }
  .eduflow-demo__timeline-header output { color:var(--muted-foreground); font:12px ui-monospace,SFMono-Regular,Consolas,monospace; }
  .eduflow-demo__timeline-track { display:flex; min-width:max-content; margin:14px 0 0; padding:0 4px 4px; list-style:none; }
  .eduflow-demo__timeline { overflow-x:auto; }
  .eduflow-demo__timeline-item { position:relative; display:grid; min-width:68px; justify-items:center; gap:6px; color:var(--muted-foreground); font-size:11px; }
  .eduflow-demo__timeline-item:not(:last-child)::after { position:absolute; top:10px; left:calc(50% + 10px); width:calc(100% - 20px); border-top:1px solid var(--border); content:''; }
  .eduflow-demo__timeline-item button { position:relative; z-index:1; width:22px; height:22px; border:1px solid var(--muted-foreground); border-radius:50%; background:var(--card); color:inherit; font-size:10px; }
  .eduflow-demo__timeline-item.is-complete button,.eduflow-demo__timeline-item.is-current button { border-color:var(--interactive); background:var(--interactive); color:var(--card); }
  .eduflow-demo__timeline-item.is-current { color:var(--foreground); font-weight:700; }
  .eduflow-demo__timeline-item.is-current button { box-shadow:0 0 0 5px color-mix(in srgb,var(--interactive) 16%,transparent); }
  .eduflow-demo__data-item { border:1px solid var(--border); border-radius:12px; background:var(--card); color:var(--foreground); transition:transform 240ms cubic-bezier(.22,1,.36,1),border-color 180ms ease,box-shadow 180ms ease; }
  .eduflow-demo__data-item.is-active { border-color:var(--interactive); color:var(--interactive); box-shadow:0 0 0 6px color-mix(in srgb,var(--interactive) 12%,transparent); }
  .eduflow-demo__data-item.is-complete { border-color:var(--success); color:var(--success); }
  .eduflow-demo__data-item.is-error { border-color:var(--error); color:var(--error); }
  body[data-experience-kind="network"] svg,
  body[data-experience-kind="hierarchy"] svg { width:100%; min-height:320px; }
  body[data-experience-kind="sequence"] [role="list"],
  body[data-experience-kind="sequence"] ol { scroll-snap-type:x proximity; }
  body[data-experience-kind="sequence"] [role="list"] > *,
  body[data-experience-kind="sequence"] ol > * { scroll-snap-align:start; }
  body[data-experience-kind="collection"] [data-value],
  body[data-experience-kind="state"] [data-state] { transition:transform 220ms ease,background 220ms ease,border-color 220ms ease; }
  body[data-experience-kind="code"] pre { overflow:auto; border:1px solid var(--border); border-radius:12px; padding:14px; background:#25231f; color:#fff8e8; }
  #root table { width:100%; border-collapse:collapse; }
  #root th,#root td { border-bottom:1px solid var(--border); padding:9px; text-align:left; }
  @media (max-width:760px) {
    body { padding:8px; }
    .eduflow-demo { padding:14px; }
    .eduflow-demo__stage { grid-template-columns:1fr; min-height:0; }
    .eduflow-demo__visual { min-height:340px; }
    .eduflow-demo__explanation { align-items:stretch; flex-direction:column; }
    .eduflow-demo__controls { justify-content:flex-start; }
  }
  @media (prefers-reduced-motion:reduce) { *,*::before,*::after { scroll-behavior:auto!important; transition-duration:1ms!important; animation-duration:1ms!important; } }
</style>
<style>${tailwindPreflight}\n${utilityCss}</style>
<style>${LEGACY_CONTROL_POLISH}</style>
</head>
<body data-experience-kind="${experienceKind}">
  <div id="root"></div>

  <!-- 3. 运行时依赖：React UMD 本地注入（不走 CDN，见文件头注释） -->
  <script>${reactUMD}</script>
  <script>${reactDOMUMD}</script>

  <!-- 4. 编译后的组件 JS（宿主侧 Babel 已转译为 React.createElement） -->
  <script>
    ${compiledJs}

    const root = ReactDOM.createRoot(document.getElementById('root'));
    root.render(React.createElement(InteractiveDemo));

    const polishLegacyControls = () => {
      const demoRoot = document.getElementById('root');
      if (!demoRoot || demoRoot.querySelector('.eduflow-demo')) return;

      const buttons = [...demoRoot.querySelectorAll('button')];
      const primary = buttons.find((button) => /自动演示|开始演示|播放|继续|运行/.test(button.textContent || ''))
        || buttons.find((button) => /下一步/.test(button.textContent || ''));
      if (primary) primary.dataset.sandboxAction = 'primary';

      buttons.forEach((button) => {
        if (/重置|重新开始|复位/.test(button.textContent || '')) button.dataset.sandboxAction = 'reset';
      });

      demoRoot.querySelectorAll('input[type="range"]').forEach((range) => {
        let panel = range.parentElement;
        while (panel && panel !== demoRoot && panel.querySelectorAll('button').length < 2) panel = panel.parentElement;
        if (panel && panel !== demoRoot) panel.dataset.sandboxControls = 'true';
      });
    };

    requestAnimationFrame(polishLegacyControls);
    new MutationObserver(polishLegacyControls).observe(document.getElementById('root'), { childList: true, subtree: true });
  </script>
</body>
</html>`;
}

// ============================================================================
// 组件
// ============================================================================

export function SandboxRenderer({ code, experienceKind = "concept" }: SandboxRendererProps) {
  const [compiled, setCompiled] = useState<string | null>(null);
  const [utilityCss, setUtilityCss] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Babel standalone 体积较大（~2.6MB），动态加载拆为独立 chunk，仅渲染时下载
  useEffect(() => {
    let cancelled = false;
    setCompiled(null);
    setUtilityCss(null);
    setError(null);

    if (!code) return;

    Promise.all([import("@babel/standalone"), compileTailwindCss(code)])
      .then(([mod, generatedCss]) => {
        if (cancelled) return;
        try {
          const result = mod.default.transform(cleanCode(code), {
            presets: [["react", { runtime: "classic" }]],
            filename: "interactive-demo.jsx",
          });
          if (!cancelled) {
            setCompiled(result.code ?? "");
            setUtilityCss(generatedCss);
          }
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
    () => (compiled === null || utilityCss === null ? "" : buildHtml(compiled, utilityCss, experienceKind)),
    [compiled, utilityCss, experienceKind],
  );

  if (!code) {
    return (
      <div className="flex items-center justify-center p-8 text-sm text-[var(--muted-foreground)]">
        这项交互内容尚未准备好，请重新生成后再试。
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-2 rounded-lg border border-[var(--error)] p-4">
        <p className="text-sm font-medium text-[var(--error)]">互动内容暂时无法展示</p>
        <p className="text-sm leading-6 text-[var(--muted-foreground)]">生成的展示格式不完整，请重新生成这项成果。</p>
      </div>
    );
  }

  if (compiled === null || utilityCss === null) {
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
      className="w-full min-h-[760px] border-0 bg-[var(--background)]"
      title="交互推演"
    />
  );
}
