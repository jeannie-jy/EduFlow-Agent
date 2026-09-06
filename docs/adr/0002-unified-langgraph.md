# ADR 0002：统一生成、审批恢复、反馈和局部重生成到 LangGraph

- 状态：Accepted
- 日期：2026-09-05

## 背景

早期实现同时存在主 Graph、手写 resume 链和独立模块调度路径，同一节点在不同入口具有不同持久化、错误和 Trace 行为。

## 决策

使用一张支持多入口的 LangGraph：Planner、Knowledge、Coder、Quality、Reflection 和 Modules 共享状态契约；教师审批使用 `interrupt`/`Command(resume=...)` 与 PostgreSQL Checkpointer；反馈、局部重生成、单模块及批量模块重试通过明确入口复用同一节点与 Trace 包装。模块内部仍由有界并发 DAG 执行，但作为 Graph 的 Modules 节点被调用；调度器在 Graph 内禁止自行持久化，由 Graph 收尾统一写入一次快照和版本。

## 结果

- 主生成与恢复不再复制业务编排逻辑；
- request/workflow/node/tool 标识可在同一次运行中关联；
- Reflection 循环、最大重规划次数和 LLM 总预算由统一状态控制；
- 模块入口不再绕过 Checkpointer/Trace，也不会为同一次生成重复创建版本；
- 代价是 Graph 状态迁移需要兼容已有 checkpoint，模块内部细粒度 checkpoint 仍待补齐。

## 被否决方案

- 每个 HTTP 入口维护独立调用链：实现快但持续产生状态漂移；
- 将所有模块拆为多个独立 Agent：当前模块多为确定性依赖与并发问题，会增加通信和评测复杂度；
- 仅依赖进程内状态：无法支持重启后的 HITL 恢复。
