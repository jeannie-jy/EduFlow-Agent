# 术语表 · Glossary

> 确保团队使用统一的语言。术语统一 = 减少返工。
>
> 代码命名优先使用英文，文档中可中英混用。本文档提供双向映射。

---

## 核心概念

| 中文 | English | 说明 |
|------|---------|------|
| 自主决策循环 | Agent Loop | Agent 自主决定思考→行动→观察的循环，区别于固定 Workflow |
| Agent 编排图 | LangGraph StateGraph | 5 个 Agent 节点组成的有向图（Planner → Knowledge → Coder → Quality → [Reflection ↺]） |
| 人在回路 | Human-in-the-Loop (HITL) | 教学计划生成后中断等待教师确认/拒绝，从断点恢复 |
| 规划 | Planning | Agent 分解知识点、构建教学步骤的过程 |
| 反思 | Reflection | Agent 根据质量报告修正 DSL 的过程 |

## Agent 角色（当前实现，5 个 LangGraph 节点）

| 中文 | English | 职责 |
|------|---------|------|
| 规划 Agent | Planner Agent | 生成教学计划（目标/大纲/策略/建议参数），输出后 HITL 中断 |
| 知识 Agent | Knowledge Agent | 从教学计划提取概念图（concepts/edges/key_terms） |
| 编码 Agent | Coder Agent | 将教学计划 + 知识图谱转为逐帧 DSL（RenderScript） |
| 质量 Agent | Quality Agent | 三层校验：Pydantic Schema + 帧间状态一致性 + LLM 六维度评分 |
| 反思 Agent | Reflection Agent | 质量不达标时修订 DSL（最多 3 轮），尊重锁定帧 |

## 记忆系统（规划中，尚未实现）

> v0.8 未实现记忆系统；早期 init.sql 中的长期记忆/轨迹表已随遗留 schema 一并移除，
> 后续按需以独立迁移引入。

| 中文 | English | 说明 |
|------|---------|------|
| 会话上下文 | Session Context | 当前生成流程的 AgentState（LangGraph checkpointer 持久化） |

## 渲染相关

| 中文 | English | 说明 |
|------|---------|------|
| 渲染脚本 | RenderScript | Coder Agent 输出的 JSON 渲染指令 |
| 渲染帧 | Render Frame | 一个完整的教学分镜 |
| 渲染动作 | Render Action | 单个渲染操作（创建节点、高亮、旋转等） |
| 推演 | Render / Visualize | 将算法逻辑以动画形式展现 |
| 分镜 | Frame | 教学序列中的一个步骤画面 |
| 视频导出 | Video Export | 将推演序列渲染为 MP4 视频（辅助功能） |
| Manim | Manim CE | 数学动画渲染引擎，用于视频导出 |

## 通信协议

| 中文 | English | 说明 |
|------|---------|------|
| 模型上下文协议 | MCP (Model Context Protocol) | LLM 与外部工具的标准化接口协议 |
| 服务端推送 | SSE (Server-Sent Events) | 前端实时接收后端推送的数据流 |

## 教学领域

| 中文 | English | 说明 |
|------|---------|------|
| 概念介绍 | Concept Intro | 引入新知识点的教学步骤 |
| 代码走读 | Code Walkthrough | 逐行讲解代码逻辑 |
| 交互式练习 | Quiz | 用户参与的练习环节 |
| 类比解释 | Analogy | 用生活化类比降低理解门槛 |
| 对比分析 | Comparison | 并列展示两种算法/结构差异 |
| 前置知识 | Prerequisites | 学习当前知识点前需掌握的内容 |

## 技术缩写

| 缩写 | 说明 |
|------|------|
| pgvector | PostgreSQL 向量检索扩展 |
| Manim CE | Mathematical Animation Community Edition |
| FFmpeg | 视频/音频编解码工具 |
| SSE | Server-Sent Events 服务端推送 |

---

## 命名对照速查

需求方说法 → 开发者对应术语：

| 需求方说法 | 开发者术语 |
|-----------|-----------|
| "推演" / "动画" | `render` / `visualize` |
| "分镜" / "一帧" | `Frame` |
| "教学步骤" | `step`（teaching_plan.outline） |
| "步骤编排" / "教案" | `teaching_plan` / `planning` |
| "动画效果" | `animation` |
| "学生练习" | `quiz` |
| "审阅" / "确认" | `approval`（HITL） |
| "纠错" | `reflection` / `correction` |
| "知识点" | `concept` |
| "导出视频" | `video export` |
