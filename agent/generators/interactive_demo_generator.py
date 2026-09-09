"""Interactive Demo Generator — Artifact 级动态可视化。

LLM 生成完整的单文件 React 组件代码字符串，
前端通过 iframe 安全沙箱（Babel + UMD React）渲染。
"""

from __future__ import annotations

import json
import logging
import re
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

**样式方案：** 必须使用下方 EduFlow 语义化 class。这些 class 由运行环境内置样式，不得依赖 Tailwind CDN，不得仅用 Tailwind utility class 构建核心布局。

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

## 统一界面结构（必须逐层使用）

```jsx
<div className="eduflow-demo">
  <header className="eduflow-demo__header">
    <div><p className="eduflow-demo__eyebrow">交互案例 · 类型</p><h2>主题标题</h2></div>
    <span className="eduflow-demo__mode">准备体验</span>
  </header>
  <div className="eduflow-demo__stage">
    <section className="eduflow-demo__visual">...</section>
    <aside className="eduflow-demo__status">
      <p className="eduflow-demo__eyebrow">实时状态</p><h3>当前状态</h3>...
    </aside>
  </div>
  <section className="eduflow-demo__explanation">
    <div className="eduflow-demo__narration"><p className="eduflow-demo__eyebrow">当前步骤</p><p>讲解文案</p></div>
    <div className="eduflow-demo__controls">...</div>
  </section>
  <section className="eduflow-demo__timeline">
    <div className="eduflow-demo__timeline-header"><p className="eduflow-demo__eyebrow">推演进度</p><output>01 / 14</output></div>
    <ol className="eduflow-demo__timeline-track">...</ol>
  </section>
</div>
```

- 右侧实时状态必须使用表格、队列、栈、变量表或关键指标中最适合当前主题的形式，并与主可视化同步更新。
- 时间轴使用 `eduflow-demo__timeline-item`，当前步骤增加 `is-current`，已完成步骤增加 `is-complete`；每个步骤都是可点击 button。
- 按钮统一使用 `eduflow-demo__button`；主操作叠加 `is-primary`，纯图标式上一步/下一步叠加 `is-icon`。禁止使用 Emoji 作为图标，图标按钮使用文字 `上一步` / `下一步` 的 `aria-label`。
- 数据元素使用 `eduflow-demo__data-item`；当前操作叠加 `is-active`，已完成叠加 `is-complete`，错误叠加 `is-error`。
- 必须在 360px 到 1600px 宽度下可用；小屏时主可视化和状态面板改为单列。

## 视觉与交互规范（必须遵守，这是界面质量的硬性要求）

1. **四段式布局**：顶部标题与模式 → 中部「核心可视化 + 实时状态」两列 → 讲解与播放控制 → 底部可点击时间轴。
2. **高信息密度**：紧凑、干净，去除一切装饰性图片/缩略图，视觉重心完全放在数据与算法逻辑上。
3. **可视化区**：
   - 数组/列表类：使用**水平排列的卡片（Card）或柱状条**，绝不用垂直纯文本列表；每个元素数值用 `font-mono` 大字显示，索引用小号浅色文字（`text-[var(--muted-foreground)]`）标注在下方。
   - 元素交换/移动必须使用 **CSS transition 平滑动画**（`transition: transform 320ms cubic-bezier(0.22, 1, 0.36, 1)`），用 `transform: translateX/Y` 过渡，禁止瞬间跳变。
   - 树/图/栈/队列等其他知识点：按同样规范个性化设计（树用连线层级、图用节点+边、栈用堆叠块等）。
4. **状态色**（使用 iframe 内的 CSS 变量，禁止写死 hex）：
   - 默认：`bg-[var(--card)]` + `border-[var(--border)]` + `text-[var(--foreground)]`
   - 正在比较/操作中：`border-[var(--interactive)]` + `text-[var(--interactive)]`（可加 10% 透明度背景）
   - 已完成/已排序：`border-[var(--success)]` + `text-[var(--success)]`
   - 错误/不匹配：`var(--error)`；进度/时间：`var(--progress)`
5. **控制面板**：一组现代化按钮（Button Group）——主操作（自动演示/下一步）用 `bg-[var(--interactive)]` 强调色按钮；次要操作（上一步）用细边框按钮；重置用幽灵按钮（仅文字，无背景）。所有按钮必须有 hover 反馈（提亮/变色）与按下反馈（`active:scale-95`），禁用态 `disabled:opacity-40`。
6. **状态与提示区**：步骤进度用 `font-mono tabular-nums` 等宽数字（如「步骤 8 / 18」）；当前操作说明用一句话明确文案（如「正在比较 4 和 8：8 > 4，需要交换」「发生交换：8 与 4 互换位置」）；可选细进度条（`var(--progress)`）。
7. **字体**：数值/索引/步骤号用等宽字体（`font-mono`），正文用默认无衬线；圆角以 `rounded-lg`/`rounded-xl` 为主，边框 `1px` 细线。
8. **禁止**：纯文本竖排列表、无样式的原生控件、Emoji 代替图标、大面积渐变/重阴影/花哨装饰、写死 Light/Dark 色值（一律用 CSS 变量）。

## 输出格式

**资源预算：** `code` 总长度不得超过 9000 字符；步骤控制在 4～8 个，
不要内联大段 CSS、SVG path 或重复保存每一步的完整数据。优先用数组 + map、
纯函数和派生状态复用数据，以减少输出长度并提高加载速度。

直接输出纯 JSX 代码字符串，以 `const InteractiveDemo = () => {` 开头，
以 `};` 结尾。不要有任何前缀或后缀文字。
"""

INTERACTIVE_DEMO_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "code": {
            "type": "string",
            "maxLength": 12000,
            "description": "完整且可编译的 React 组件 JSX 代码字符串",
        },
    },
    "required": ["code"],
}


def _normalize_interactive_code(value: Any) -> str:
    """Remove transport-only markdown fences without altering program text."""
    if not isinstance(value, str):
        return ""
    code = value.strip()
    if code.startswith("```"):
        code = re.sub(r"^```(?:jsx|tsx|javascript|js)?\s*", "", code, count=1)
        code = re.sub(r"\s*```$", "", code, count=1)
    return code.strip()


def _has_balanced_delimiters(source: str) -> bool:
    """Cheap deterministic corruption check for generated JSX.

    This is intentionally not a JavaScript parser, but it reliably catches the
    dominant failure mode here: a response cut inside a string, expression,
    array, or component body. The browser's Babel compiler remains the final
    sandbox boundary.
    """
    pairs = {")": "(", "]": "[", "}": "{"}
    stack: list[str] = []
    quote = ""
    escaped = False
    line_comment = False
    block_comment = False
    index = 0
    while index < len(source):
        char = source[index]
        nxt = source[index + 1] if index + 1 < len(source) else ""
        if line_comment:
            if char == "\n":
                line_comment = False
            index += 1
            continue
        if block_comment:
            if char == "*" and nxt == "/":
                block_comment = False
                index += 2
            else:
                index += 1
            continue
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            index += 1
            continue
        if char == "/" and nxt == "/":
            line_comment = True
            index += 2
            continue
        if char == "/" and nxt == "*":
            block_comment = True
            index += 2
            continue
        if char in "'\"`":
            quote = char
        elif char in "([{":
            stack.append(char)
        elif char in ")]}":
            if not stack or stack.pop() != pairs[char]:
                return False
        index += 1
    return not stack and not quote and not block_comment


def _fallback_interactive_code(context: dict[str, Any]) -> str:
    """Build a compact, always-runnable stepper without another LLM call."""
    topic = str(context.get("topic") or "课程主题")[:120]
    concepts = [str(item)[:80] for item in context.get("concepts", [])[:8] if item]
    outline = [str(item)[:100] for item in context.get("outline", [])[:8] if item]
    objectives = [str(item)[:140] for item in context.get("objectives", [])[:6] if item]
    titles = outline or objectives or concepts or ["概念导入", "关键过程", "总结"]
    steps = [
        {
            "title": title,
            "narration": (
                objectives[index % len(objectives)]
                if objectives
                else f"观察并理解 {title}。"
            ),
        }
        for index, title in enumerate(titles[:8])
    ]
    payload = json.dumps(
        {"topic": topic, "concepts": concepts, "steps": steps},
        ensure_ascii=False,
        separators=(",", ":"),
    ).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return f"""const demoData = {payload};
const InteractiveDemo = () => {{
  const [step, setStep] = React.useState(0);
  const current = demoData.steps[step];
  const last = demoData.steps.length - 1;
  const move = (next) => setStep(Math.max(0, Math.min(last, next)));
  return (
    <div className="eduflow-demo">
      <header className="eduflow-demo__header">
        <div><p className="eduflow-demo__eyebrow">交互案例 · 概念推演</p><h2>{{demoData.topic}}</h2></div>
        <span className="eduflow-demo__mode">步骤 {{step + 1}} / {{demoData.steps.length}}</span>
      </header>
      <div className="eduflow-demo__stage">
        <section className="eduflow-demo__visual">
          <div role="list" style={{{{display:'flex',flexWrap:'wrap',gap:12,alignItems:'center',justifyContent:'center'}}}}>
            {{(demoData.concepts.length ? demoData.concepts : demoData.steps.map(item => item.title)).map((item, index) => (
              <div key={{item + index}} role="listitem" className={{`eduflow-demo__data-item ${{index === step ? 'is-active' : index < step ? 'is-complete' : ''}}`}} style={{{{padding:'16px 18px',minWidth:120,textAlign:'center'}}}}>
                <span style={{{{fontFamily:'ui-monospace,monospace',fontWeight:700}}}}>{{item}}</span>
              </div>
            ))}}
          </div>
        </section>
        <aside className="eduflow-demo__status">
          <p className="eduflow-demo__eyebrow">实时状态</p><h3>{{current.title}}</h3>
          <p>{{current.narration}}</p>
          <p style={{{{marginTop:12}}}}>已完成 {{step}} 个步骤，剩余 {{last - step}} 个步骤。</p>
        </aside>
      </div>
      <section className="eduflow-demo__explanation">
        <div className="eduflow-demo__narration"><p className="eduflow-demo__eyebrow">当前步骤</p><p>{{current.narration}}</p></div>
        <div className="eduflow-demo__controls">
          <button className="eduflow-demo__button is-icon" aria-label="上一步" disabled={{step === 0}} onClick={{() => move(step - 1)}}>上一步</button>
          <button className="eduflow-demo__button" onClick={{() => setStep(0)}}>重置</button>
          <button className="eduflow-demo__button is-primary is-icon" aria-label="下一步" disabled={{step === last}} onClick={{() => move(step + 1)}}>下一步</button>
        </div>
      </section>
      <section className="eduflow-demo__timeline">
        <div className="eduflow-demo__timeline-header"><p className="eduflow-demo__eyebrow">推演进度</p><output>{{String(step + 1).padStart(2,'0')}} / {{String(demoData.steps.length).padStart(2,'0')}}</output></div>
        <ol className="eduflow-demo__timeline-track">
          {{demoData.steps.map((item, index) => <li key={{item.title + index}} className={{`eduflow-demo__timeline-item ${{index === step ? 'is-current' : index < step ? 'is-complete' : ''}}`}}><button onClick={{() => move(index)}}>{{index + 1}}</button><span>{{item.title}}</span></li>)}}
        </ol>
      </section>
    </div>
  );
}};"""


class InteractiveDemoGenerator(BaseGenerator):
    """交互式演示生成器。

    生成可运行的 React 组件代码，前端沙箱渲染。
    """

    module_id = "interactive_demo"
    display_name = "交互推演"
    description = "生成可交互的算法可视化 React 组件（沙箱渲染），支持逐步操作和实时反馈"
    icon = "play"
    category = "interactive"
    priority = 10
    version = "1.0.0"
    temperature = 0.3
    max_tokens = 8192

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

    async def generate(
        self,
        teaching_plan: dict[str, Any],
        knowledge_graph: dict[str, Any],
        user_input: str,
        constraints: dict[str, Any],
        project_id: str,
        existing_outputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate one compact component, falling back locally when corrupt.

        A malformed source artifact is never repaired by slicing or by another
        paid model call. The deterministic fallback keeps the workbench usable
        and makes latency bounded even when the provider ignores the contract.
        """
        context = self._build_context(
            teaching_plan,
            knowledge_graph,
            user_input,
            constraints,
        )
        try:
            result = await self._call_llm(context)
            normalized = {
                **result,
                "code": _normalize_interactive_code(result.get("code")),
            }
            blocking = [
                issue for issue in self.validate(normalized)
                if issue.get("severity") == "high"
            ]
            if not blocking:
                normalized["generation_mode"] = "llm"
                return normalized
            reason = ",".join(str(issue.get("type")) for issue in blocking)
            logger.warning(
                "Interactive demo rejected; using deterministic fallback | reason=%s",
                reason,
            )
        except Exception as exc:
            reason = type(exc).__name__
            logger.warning(
                "Interactive demo generation unavailable; using deterministic fallback | error=%s",
                reason,
            )

        return {
            "code": _fallback_interactive_code(context),
            "generation_mode": "deterministic_fallback",
            "fallback_reason": reason,
        }

    def validate(self, output):
        issues = super().validate(output)
        if any(i["severity"] == "high" and i["type"] == "schema_error" for i in issues):
            return issues
        code = output.get("code", "")
        if not isinstance(code, str):
            issues.append({
                "severity": "high",
                "type": "invalid_code_type",
                "description": f"code 不是字符串: {type(code).__name__}",
            })
            return issues
        if len(code) < 50:
            issues.append({"severity": "high", "type": "too_short", "description": f"代码过短 ({len(code)} 字符)"})
            return issues
        if len(code) > 12000:
            issues.append({
                "severity": "high",
                "type": "code_too_long",
                "description": f"代码超过交互运行时预算 ({len(code)} > 12000 字符)",
            })
        if not re.search(r"\b(?:const|function)\s+InteractiveDemo\b", code):
            issues.append({
                "severity": "high",
                "type": "missing_component",
                "description": "缺少 InteractiveDemo 组件定义",
            })
        if "return" not in code or not _has_balanced_delimiters(code):
            issues.append({
                "severity": "high",
                "type": "incomplete_code",
                "description": "JSX 字符串、括号或组件主体不完整",
            })
        if re.search(
            r"(?:\bimport\s|\brequire\s*\(|\bfetch\s*\(|XMLHttpRequest|localStorage)",
            code,
        ):
            issues.append({
                "severity": "high",
                "type": "forbidden_runtime_api",
                "description": "代码包含沙箱禁止的导入、网络或持久化 API",
            })
        if code.strip().startswith("```"):
            issues.append({"severity": "low", "type": "markdown_wrapped", "description": "代码被 markdown 包裹，前端会自动剥离"})
        return issues


register_generator(InteractiveDemoGenerator())
logger.info("InteractiveDemoGenerator 已注册 (module_id=interactive_demo)")
