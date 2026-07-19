# Effect provenance

| Local file | Upstream component | Exact URL | License | Installed dependencies | Local modifications |
| --- | --- | --- | --- | --- | --- |
| `WorkspaceGrid.tsx` | Magic UI Animated Grid Pattern | `https://magicui.design/docs/components/animated-grid-pattern` | MIT | `motion@^12.42.2` | Wrapped the installed `@magicui/animated-grid-pattern` source with semantic CSS variables, an `aria-hidden`/pointer-inert container, and a static SVG fallback shown when reduced motion is requested. |
| `GenerationBorder.tsx` | Magic UI Border Beam | `https://magicui.design/docs/components/border-beam` | MIT | `motion@^12.42.2` | Wrapped the installed `@magicui/border-beam` source so it exists only during `planning`, receives semantic theme colors, is inaccessible and pointer-inert, and leaves a static border when reduced motion is requested. The installed source has one TypeScript-only import compatibility correction for this project's `verbatimModuleSyntax` setting. |

No Spotlight, Tracing Beam, Text Generate Effect, Uiverse control, page transition, or additional animation library is included. The animated grid and planning border beam are the full continuous-animation budget for the current workbench.
