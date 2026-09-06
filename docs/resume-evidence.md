# EduFlow-Agent 简历证据清单

> 更新日期：2026-09-06。仅记录可由当前代码、数据集或本地门禁复验的事实；在线模型结果、
> 真实容器容量与人工评分未完成前不得写成已取得指标。

## 可直接引用的数据

| 证据 | 当前值 | 复验入口 |
|---|---:|---|
| 后端完整测试 | 1051 passed | Python 3.12 虚拟环境运行 `python -m pytest agent/tests -q`；含真实 Manim 渲染用例，无 skip |
| 前端测试 | 41 files / 295 tests | `cd web && npm run test` |
| 核心质量案例 | 50 | `agent/evals/datasets/eduflowbench_v1.jsonl` |
| Prompt Injection 案例 | 8 | `agent/evals/datasets/injection_cases.jsonl` |
| 检索案例 | 10 | `agent/evals/datasets/retrieval_cases.jsonl` |
| 确定性 Tool 案例 | 16 | `agent/evals/datasets/tool_cases.jsonl` |
| 在线 Tool 案例入口 | 8 | `agent/evals/datasets/tool_online_cases.jsonl`；尚无真实模型分数 |
| 生产 Tool 数量 | 3 个只读工具 | `knowledge_search` / `material_lookup` / `get_project_context` |
| 主入口拆包变化 | 1342.14 kB → 547.38 kB（-59.2%） | `cd web && npm run build`；当前 gzip 177.94 KiB，预算 250 KiB |

## 当前不可作为结果指标引用的数据

- 真实模型 DSL 正确率、groundedness、Judge 得分与 Reflection 提升幅度；
- 真实模型 Tool selection accuracy、task completion rate、Token、成本与 p95；
- Manim 首次渲染成功率（本机未安装 Manim，CI 已有真实 render job）；
- Docker Compose 故障恢复、容量 RPS/p95 和多副本结论（已有脚本/手动 CI，尚无本机报告）；
- 人工评审与 LLM Judge 的一致率/Kappa（已有匿名抽样和计算器，尚未完成标注）。

## 最终推荐版（当前可投递）

**EduFlow：基于 LangGraph 的教学推演 Agent 系统｜核心开发者**
技术栈：Python / FastAPI / LangGraph / PostgreSQL + pgvector / Redis / MinIO / Docker

面向计算机科学教学内容生产的有状态 Agent 系统，通过规划、检索、工具调用、质量反思和
教师审批，将课程主题与材料转换为可交互、可编辑、可评估的逐帧教学 DSL，并支持 Web 与
Manim 双端渲染。

- 设计 Planner–Knowledge–Coder–Quality–Reflection LangGraph 工作流，以 PostgreSQL Checkpointer 与 HITL Interrupt 统一生成、审批恢复、反馈修订和局部重生成，并将模块依赖建模为有界并发 DAG。
- 构建受控多轮 Tool Calling Runtime，接入 3 个真实只读工具，以 Pydantic Schema、owner 二次鉴权、轮次/调用/并发/结果预算及持久化 Tool Trace 约束模型执行，并建设 16 个确定性与 8 个在线 Tool 案例。
- 将 pgvector 多查询、RRF、上下文预算、来源引用和不可信内容隔离接入生成主链，建设含 50 个核心、10 个检索及 8 个注入案例的 EduFlowBench，并提供独立 Judge、成本闸门和匿名人工校准流程。
- 设计 RenderScript DSL 与确定性 Guardrails，以状态不变量、锁帧、影响分析和范围合并约束模型输出；Frames 真源、不可变 ProjectVersion 与版本绑定导出支持局部重算及可追溯恢复。
- 建设 LLM Gateway、PostgreSQL lease Worker、持久化 SSE 与无网络/无凭据执行沙箱，覆盖重试/熔断/fallback、Token/成本限制、审计归档和故障恢复；当前后端 1051 项、前端 295 项测试通过。

## 面试陈述边界

- 可以说“真实 Tool Calling 已进入生产 Knowledge 主链”，不能说“已达到某个真实模型工具选择率”。
- 可以说“提供 MCP/Skill 扩展方向”，不能说“已实现 MCP 或 Skill”；当前是进程内 typed Registry。
- 可以说“模块 DAG 并发协作”，不能包装为自由协商式 Multi-Agent；当前未实现独立多 Agent 协商。
- 可以说“具备签名归档、Prometheus/Grafana 和持久化 Trace”，不能说已有生产流量或长期运行数据。
