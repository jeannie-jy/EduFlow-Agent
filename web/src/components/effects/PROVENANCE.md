# Effect provenance

English | [简体中文](PROVENANCE.zh-CN.md)

| Local file | Upstream component | Exact URL | License | Installed dependencies | Local modifications |
| --- | --- | --- | --- | --- | --- |
| `WorkspaceGrid.tsx` | Magic UI Animated Grid Pattern | `https://magicui.design/docs/components/animated-grid-pattern` | MIT | `motion@^12.42.2` | The upstream source is isolated at `effects/magicui/animated-grid-pattern.tsx`, lazy-loaded after first paint/idle, and uses the local `effects/magicui/motion.ts` dynamic bridge so Motion is fetched only after the lazy effect path. The wrapper provides semantic CSS variables, an `aria-hidden`/pointer-inert container, and a static SVG fallback for reduced motion or unavailable `ResizeObserver`. |
| `GenerationBorder.tsx` | Magic UI Border Beam | `https://magicui.design/docs/components/border-beam` | MIT | `motion@^12.42.2` | The upstream source is isolated at `effects/magicui/border-beam.tsx`, lazy-loaded only during `planning` after first paint/idle, and uses the local `effects/magicui/motion.ts` dynamic bridge. The wrapper provides semantic colors, an `aria-hidden`/pointer-inert container, and a static reduced-motion border. It has one TypeScript-only import compatibility correction for this project's `verbatimModuleSyntax` setting. |

No Spotlight, Tracing Beam, Text Generate Effect, Uiverse control, page transition, or additional animation library is included. The animated grid and planning border beam are the full continuous-animation budget for the current workbench.
