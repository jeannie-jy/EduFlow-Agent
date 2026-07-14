# 术语表 · Glossary

> 确保团队使用统一的语言。术语统一 = 减少返工。
>
> 代码命名优先使用英文，文档中可中英混用。本文档提供双向映射。

---

## 核心概念

| 中文 | English | 说明 |
|------|---------|------|
| 自主决策循环 | Agent Loop | Agent 自主决定思考→行动→观察的循环，区别于固定 Workflow |
| 有向无环任务图 | Task DAG | 带依赖关系的教学步骤图结构 |
| 思考-行动-观察 | ReAct (Reasoning + Acting) | Agent 决策框架三要素 |
| 人在回路 | Human-in-the-Loop (HITL) | 关键决策需人类确认的交互模式 |
| 规划 | Planning | Agent 分解知识点、构建教学步骤的过程 |
| 反思 | Reflection | Agent 分析失败原因并调整策略的能力 |

## Agent 角色（初步设计）

| 中文 | English | 职责 |
|------|---------|------|
| 规划 Agent | Planner Agent | 分解知识点、构建教学步骤 DAG、选择工具 |
| 编码 Agent | Coder Agent | 将教学计划转为渲染指令 JSON |
| 校验 Agent | Validator Agent | 校验输出结构的完整性和正确性 |
| 反思 Agent | Reflection Agent | 失败根因分析、策略调整、经验抽取 |

## 记忆系统

| 中文 | English | 说明 |
|------|---------|------|
| 工作记忆 | Working Memory | 当前会话上下文，会话结束清空 |
| 短期记忆 | Short-Term Memory | 最近几轮会话的关键信息，滑动窗口 |
| 长期记忆 | Long-Term Memory | 永久存储的成功模板、失败案例、用户偏好 |
| 记忆衰减 | Memory Decay | 不常用记忆随时间降低重要性 |

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
| "分镜" / "一帧" | `RenderFrame` |
| "教学步骤" | `TaskNode` / `step` |
| "步骤编排" / "教案" | `TaskGraph` / `planning` |
| "动画效果" | `easing` / `animation` |
| "学生练习" | `quiz` |
| "审阅" / "确认" | `approval` |
| "纠错" | `reflection` / `correction` |
| "学习记录" | `trajectory` / `memory` |
| "知识点" | `concept` |
| "导出视频" | `video export` |
