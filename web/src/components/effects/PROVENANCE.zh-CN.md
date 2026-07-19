# 动效来源说明

[English](PROVENANCE.md) | 简体中文

| 本地文件 | 上游组件 | 准确地址 | 许可证 | 安装依赖 | 本地修改 |
| --- | --- | --- | --- | --- | --- |
| `WorkspaceGrid.tsx` | Magic UI Animated Grid Pattern | `https://magicui.design/docs/components/animated-grid-pattern` | MIT | `motion@^12.42.2` | 上游源码隔离在 `effects/magicui/animated-grid-pattern.tsx`，在首屏完成或浏览器空闲后懒加载；通过本地 `effects/magicui/motion.ts` 动态桥接，仅在进入该动效路径后加载 Motion。包装组件使用语义 CSS 变量，容器设为 `aria-hidden` 且不接收指针事件，并为减少动态效果偏好或缺少 `ResizeObserver` 的环境提供静态 SVG 降级。 |
| `GenerationBorder.tsx` | Magic UI Border Beam | `https://magicui.design/docs/components/border-beam` | MIT | `motion@^12.42.2` | 上游源码隔离在 `effects/magicui/border-beam.tsx`，仅在 `planning` 状态下于首屏完成或浏览器空闲后懒加载，并使用本地 Motion 动态桥接。包装组件提供语义颜色、`aria-hidden` 且不接收指针事件的容器，以及减少动态效果时的静态边框；另包含一处针对本项目 `verbatimModuleSyntax` 设置的 TypeScript 导入兼容修正。 |

当前工作台没有使用 Spotlight、Tracing Beam、Text Generate Effect、Uiverse 控件、页面切换动画或其他动画库。动画网格和生成中边框光束构成当前工作台全部持续动画预算。

