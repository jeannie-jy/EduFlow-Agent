# ADR 0004：采用受控只读 Tool Calling Runtime

- 状态：Accepted
- 日期：2026-09-05

## 背景

仅在 Prompt 中拼接检索结果不能证明模型具备工具选择能力；反过来，把 Shell、SQL、
文件系统或任意 HTTP 直接暴露给模型，会把模型的不确定输出升级为服务端权限。工具还
必须继承项目 owner 边界，并能在多轮推理、并发请求和失败后留下可评测证据。

## 决策

在 Knowledge 节点前置一个 OpenAI-compatible 多轮 Tool Calling 循环。Registry 首版只
注册 `knowledge_search`、`material_lookup`、`get_project_context` 三个只读工具；模型只
提供业务参数，`project_id`、actor、role、request/workflow/node 标识由服务端注入。
Runtime 在执行前进行 Pydantic Schema 与 owner 校验，并限制总轮数、调用数、事件循环级
共享并发、单调用超时、整体 deadline 和结果字符预算。结构化 ToolResult 作为不可信数据
回填模型，脱敏 Trace 持久化工具版本、状态、耗时和摘要。

## 结果

- 模型能够真实选择并消费项目服务，而不是由代码预先固定每次工具调用；
- 未注册工具和跨 owner 访问 fail-closed，Shell、任意 SQL/文件/HTTP 不在能力面内；
- Tool selection、状态、预算、权限和注入行为可由离线 16 例及在线 8 例回归；
- 首版没有写工具，因而也没有写操作审批、幂等键和补偿协议；若新增写工具，必须先补齐
  这些协议再进入 Registry；
- MCP 与 Skill **尚未实现**。当前 `ToolSpec` 是进程内适配边界，未来接入 MCP 时仍需复用
  同一服务端身份、策略、预算和 Trace，不能把 MCP server 的声明直接视为可信授权。

## 被否决方案

- 仅把检索结果拼进 Prompt：无法衡量自主工具选择，也不支持多工具组合；
- 暴露通用 Shell/SQL/HTTP 工具：权限面过大且难以建立可证明的不变量；
- 每个 Graph 节点各自实现调用循环：会造成预算、错误语义和 Trace 漂移；
- 首版直接上多 Agent 工具协作：当前问题是证据路由而非角色协商，会增加延迟和评测维度。
