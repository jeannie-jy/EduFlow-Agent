# ADR 0001：以 RenderScript DSL 作为 Agent 与渲染器的边界

- 状态：Accepted
- 日期：2026-09-05

## 背景

教学推演同时需要 Web 交互、逐帧编辑、状态校验和 Manim 视频。若让模型分别生成 React 与 Python，两个输出会产生语义漂移，也难以锁帧、局部重算和版本比较。

## 决策

模型只生成受 Pydantic/JSON Schema 约束的 RenderScript。Frame 包含稳定 `frame_id`、视觉对象、动画、讲解和 `state_snapshot`；Web 与 Manim Adapter 都消费同一 DSL。确定性 Guardrail 在渲染前检查对象引用、状态连续性和允许的动画/对象类型。

## 结果

- 一个语义产物支持双端渲染、版本存档和结构化 diff；
- 局部重生成可按稳定 ID 合并，并保护范围外及锁定帧；
- 参数依赖能映射到 Frame 并传播到状态后继；
- 代价是 DSL 演进需要版本兼容，复杂视觉表现受 DSL 表达能力限制。

## 被否决方案

- 直接让模型生成前端代码：可控性和安全边界不足；
- Web/Manim 各生成一份脚本：无法保证语义一致；
- 只保存视频：失去编辑、校验和可访问的中间状态。
