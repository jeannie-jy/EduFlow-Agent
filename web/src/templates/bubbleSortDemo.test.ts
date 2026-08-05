/**
 * 冒泡排序交互推演模板 — 沙箱可运行性测试。
 *
 * 验证链路与 SandboxRenderer 的 iframe 执行路径一致：
 * 模板字符串 → Babel standalone 转译 JSX（classic runtime）→ 在全局 React 环境执行 → 渲染断言。
 */

import { describe, expect, it } from "vitest";
import Babel from "@babel/standalone";
import * as React from "react";
import { renderToString } from "react-dom/server";
import { bubbleSortInteractiveDemo } from "./bubbleSortDemo";

/** 模拟沙箱执行：转译 JSX 后在注入 React 全局的环境中取出 InteractiveDemo */
function compileAndGetComponent(): React.ComponentType {
  const result = Babel.transform(bubbleSortInteractiveDemo, {
    presets: [["react", { runtime: "classic" }]],
    filename: "interactive-demo.jsx",
  });
  const factory = new Function(
    "React",
    '"use strict";\n' + (result.code ?? "") + "\nreturn InteractiveDemo;",
  );
  return factory(React) as React.ComponentType;
}

describe("bubbleSortInteractiveDemo 模板", () => {
  it("Babel 转译无语法错误（沙箱可编译）", () => {
    const result = Babel.transform(bubbleSortInteractiveDemo, {
      presets: [["react", { runtime: "classic" }]],
      filename: "interactive-demo.jsx",
    });
    expect(result.code).toBeTruthy();
    expect(result.code).toContain("InteractiveDemo");
    // classic runtime：不产生 import 语句（沙箱无法执行 ESM）
    expect(result.code).not.toContain("import ");
  });

  it("渲染出三段式布局：状态区 / 可视化区 / 控制面板", () => {
    const InteractiveDemo = compileAndGetComponent();
    const html = renderToString(React.createElement(InteractiveDemo));

    // 整体容器（强制布局规范）
    expect(html).toContain("flex flex-col gap-4 p-4 bg-gray-50 rounded-xl border border-gray-200");

    // 状态说明区：高信息密度小卡片（无图标）+ 步骤指示
    expect(html).toContain("bg-blue-50 text-blue-700 rounded-md");
    expect(html).toContain("准备开始");
    expect(html).toContain("步骤");
    // SSR 会在表达式间插入 <!-- --> 注释
    expect(html).toMatch(/\/ <!-- -->\d+<\/span>/);

    // 核心可视化区：水平柱状图（flex-row，绝对禁止垂直列表）
    expect(html).toContain("flex flex-row items-end justify-center gap-2 h-48 w-full");
    expect(html).toContain("索引<!-- -->0");
    expect(html).toContain("索引<!-- -->8");
    // 柱状图：动态高度（value * 16）+ 平滑过渡
    expect(html).toContain("transition-all duration-300");
    expect(html).toContain("height:144px"); // 最大值 9 * 16

    // 控制面板：按钮组（主按钮深色强调）
    expect(html).toContain("重置");
    expect(html).toContain("上一步");
    expect(html).toContain("自动演示");
    expect(html).toContain("下一步");
    expect(html).toContain("bg-gray-900 text-white hover:bg-gray-800");
  });

  it("初始数组 9 个元素全部渲染为柱状图", () => {
    const InteractiveDemo = compileAndGetComponent();
    const html = renderToString(React.createElement(InteractiveDemo));
    for (const v of [8, 4, 6, 2, 9, 1, 5, 3, 7]) {
      expect(html).toContain(String(v));
    }
    // 9 根柱子（索引标注计数）
    const cardMatches = html.match(/索引<!-- -->\d/g);
    expect(cardMatches).toHaveLength(9);
  });

  it("不使用 import/export（沙箱清洗后仍可运行）", () => {
    expect(bubbleSortInteractiveDemo).not.toMatch(/^\s*import\s/m);
    expect(bubbleSortInteractiveDemo).not.toMatch(/export\s+default/);
    // 使用全局 React API 而非解构
    expect(bubbleSortInteractiveDemo).toContain("React.useMemo");
    expect(bubbleSortInteractiveDemo).toContain("React.useState");
  });
});
