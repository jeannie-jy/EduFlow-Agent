"""Interactive Demo Generator — Artifact 级动态可视化。

LLM 生成完整的单文件 React 组件代码字符串，
前端通过 iframe 安全沙箱（Babel + UMD React）渲染。
"""

from __future__ import annotations

import logging
from typing import Any

from .base import BaseGenerator
from .registry import register_generator

logger = logging.getLogger(__name__)

INTERACTIVE_DEMO_SYSTEM_PROMPT = """你是一位高级前端可视化工程师，擅长将算法和数据结构转化为交互式 React 可视化组件。

## 你的任务

根据教学计划和知识图谱，直接生成一段**完整的、单文件的、可交互的 React 组件代码**。

## 输出代码规范

**组件命名：** 必须导出名为 `InteractiveDemo` 的默认组件。

**状态管理：** 使用 `useState`、`useEffect` 等 Hook 管理交互状态。

**样式方案：** 使用 Tailwind CSS class 控制布局和样式。

**颜色规范（必须严格遵守）：**
- 主交互色：`var(--interactive)` — 用于按钮、链接、选中态
- 成功/正确色：`var(--success)` — 用于已完成、正确结果
- 错误/风险色：`var(--error)` — 用于错误、不匹配
- 前景/文字色：`var(--foreground)` — 用于标题、正文
- 次级文字色：`var(--muted-foreground)` — 用于说明、元数据
- 边框色：`var(--border)` — 用于表格、卡片、分隔

**禁止使用 React 内部导入（import 语句）。** 所有 React API 通过全局变量访问：
- `React.useState(...)`（不是 `useState(...)`，不要从 'react' 导入）
- `React.useEffect(...)`
- `React.useCallback(...)`
- `React.useMemo(...)`
- `React.useRef(...)`

**正确示例：**
```jsx
const InteractiveDemo = () => {
  const [step, setStep] = React.useState(0);
  return <div className="p-4">...</div>;
};
```

**交互要求：**
- 必须有至少一个可交互控件（按钮、滑块、输入框等）
- 支持逐步演示（如"下一步"按钮推进算法步骤）
- 视觉上清晰展示算法的**数据结构和状态变化**

**可视化风格：**
- 数组排序类：用一排带数字的格子，高亮当前比较/交换的元素
- 图算法类：用节点+连线展示遍历过程
- 栈/队列类：用竖直/水平排列的元素展示 push/pop 过程
- 树结构类：用缩进或连线展示节点层级

**禁止事项：**
- 禁止使用 `fetch()`、`XMLHttpRequest`、`localStorage`
- 禁止 `export default` 之外的 export
- 禁止 import/require 语句
- 代码不要用 markdown 代码块包裹（```），直接输出纯 JSX 代码

## 输出格式

直接输出纯 JSX 代码字符串，以 `const InteractiveDemo = () => {` 开头，
以 `};` 结尾。不要有任何前缀或后缀文字。
"""

INTERACTIVE_DEMO_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "code": {"type": "string", "description": "完整的 React 组件 JSX 代码字符串"},
    },
    "required": ["code"],
}


class InteractiveDemoGenerator(BaseGenerator):
    """交互式演示生成器。

    生成可运行的 React 组件代码，前端沙箱渲染。
    """

    module_id = "interactive_demo"
    display_name = "交互演示"
    description = "生成可交互的算法可视化 React 组件（沙箱渲染）"
    icon = "play"
    category = "interactive"
    priority = 10
    version = "1.0.0"
    temperature = 0.3
    max_tokens = 16384

    @property
    def output_schema(self) -> dict[str, Any]:
        return INTERACTIVE_DEMO_OUTPUT_SCHEMA

    def get_system_prompt(self) -> str:
        return INTERACTIVE_DEMO_SYSTEM_PROMPT

    def _build_context(self, teaching_plan, knowledge_graph, user_input, constraints):
        concepts = knowledge_graph.get("concepts", [])
        return {
            "topic": user_input,
            "objectives": teaching_plan.get("objectives", []),
            "approach": teaching_plan.get("teaching_approach", ""),
            "concepts": [c.get("name") for c in concepts],
            "outline": [s.get("title", "") for s in teaching_plan.get("outline", [])],
        }

    def validate(self, output):
        issues = super().validate(output)
        if any(i["severity"] == "high" and i["type"] == "schema_error" for i in issues):
            return issues
        code = output.get("code", "")
        if len(code) < 50:
            issues.append({"severity": "high", "type": "too_short", "description": f"代码过短 ({len(code)} 字符)"})
            return issues
        if code.strip().startswith("```"):
            issues.append({"severity": "warn", "type": "markdown_wrapped", "description": "代码被 markdown 包裹，前端会自动剥离"})
        return issues


register_generator(InteractiveDemoGenerator())
logger.info("InteractiveDemoGenerator 已注册 (module_id=interactive_demo)")
