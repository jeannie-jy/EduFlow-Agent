# EduFlow-Agent 工程化改造与 EduFlowBench 实施计划

> 文档状态：Draft v1.0  
> 制定日期：2026-09-03  
> 适用版本：EduFlow-Agent v0.8.x  
> 核心目标：以“可作为 Agent 开发岗位代表项目”为标准，在不继续扩张功能面的前提下，补齐评测、可靠性、安全、可观测性和交付能力。

---

## 1. 改造目标与完成标准

本轮改造不以增加第 11、12 个成果模块为目标，而是把已有能力从“功能可演示”提升到“结果可度量、流程可恢复、问题可追踪、执行可隔离、部署可复现”。

最终应满足以下五个结果：

1. **可评估**：建立 EduFlowBench，能够比较 Prompt、模型、检索和工作流版本，阻止质量回归。
2. **可恢复**：所有长任务具有持久化状态、幂等执行、失败重试和进程重启恢复能力。
3. **可解释**：一次生成能够追踪经过的节点、检索证据、Token、成本、耗时、重试与质量变化。
4. **可安全部署**：LLM 生成代码不在 API 进程内直接执行，项目、文件和任务具备用户级权限边界。
5. **可复现交付**：依赖锁定，前后端 CI 全绿，容器与文档一致，部署具有 readiness/liveness 检查。

### 1.1 项目对外定位

改造完成前，项目应描述为：

> 基于 LangGraph 的五阶段 Agentic Workflow 教学推演系统。

满足以下条件后，才建议描述为完整的 RAG Agent 系统：

- 检索节点进入实际生成主链；
- 生成结果保留来源引用；
- 存在 retrieval/groundedness 指标；
- 检索失败和低置信结果有明确降级策略。

满足以下条件后，才建议强调“生产级”：

- 长任务可恢复；
- 生成代码隔离执行；
- 鉴权和租户隔离完成；
- 关键链路有监控、告警和容量边界；
- CI、迁移、容器部署均可复现。

---

## 2. 当前基线与已知缺陷

### 2.1 已有优势

- Planner → Knowledge → Coder → Quality → Reflection 五阶段工作流。
- HITL 教学计划审批与 Postgres Checkpointer。
- RenderScript DSL 驱动 React 交互推演和 Manim 视频。
- Registry + Protocol/BaseGenerator 模块生成体系。
- Schema、状态一致性、LLM 六维质量评价与 Reflection。
- SSE 进度、帧编辑、锁定、反馈、版本恢复和模块重试。
- PostgreSQL、pgvector、Redis、Alembic、Docker Compose。
- Prompt Injection、Schema 边界、生成器、API 和 Manim Validator 测试。

### 2.2 经验证的工程基线

- 后端当前收集到 **793** 个测试；现有 README 中的 731 已过期。
- 在本地环境中，排除真实 Manim 渲染后主要后端测试可通过；5 个真实渲染用例受 Windows 临时目录权限影响而报错。
- 前端 TypeScript 类型检查通过。
- 前端生产构建通过，但存在约 1.34 MB 主 JS 与约 2.30 MB Babel Chunk。
- 前端 278 个测试中 276 个通过，2 个 SandboxRenderer 测试因异步运行时加载未完成而失败。
- 当前 GitHub Actions 只有后端 CI。

### 2.3 缺陷清单

| 编号 | 缺陷 | 影响 | 优先级 |
|---|---|---|---|
| D01 | 前端测试非全绿，README 测试数字过期 | 项目可信度、CI | P0 |
| D02 | LLM 生成的 Manim Python 在 API 所在环境执行 | 远程代码执行、资源滥用 | P0，公开部署阻断项 |
| D03 | 缺少领域 Agent Eval，只能证明代码运行，不能证明输出质量 | Agent 能力不可量化 | P0 |
| D04 | LangGraph、手动恢复链和 ModuleDispatcher 三套编排逻辑并存 | 状态漂移、维护成本 | P0 |
| D05 | pgvector 仅作为独立 API，未进入生成主链 | 不能形成真实 RAG 闭环 | P0 |
| D06 | 模块生成顺序执行，没有依赖 DAG 和受控并发 | 时延高、资源不可控 | P1 |
| D07 | 视频和反馈任务依赖线程池/`asyncio.create_task` | 重启丢任务、无法可靠重试 | P1 |
| D08 | 缺少工作流级 Trace、成本和阶段指标 | 难定位、难优化 | P1 |
| D09 | DSL Snapshot、Frames 表、Module Outputs 多份真源 | 编辑冲突、导出内容漂移 | P1 |
| D10 | 登录仅为前端模拟，缺少后端授权 | 数据越权、无法多租户部署 | P1，公开部署阻断项 |
| D11 | Python 依赖未锁定，MinIO 使用 `latest` | 构建不可复现 | P1 |
| D12 | Docker Compose 无 Web 服务，却被描述为全容器化 | 文档与交付不一致 | P1 |
| D13 | 健康检查只返回版本，不检查 DB、Redis、Worker、存储 | 编排系统无法判断就绪 | P1 |
| D14 | DB/Redis 生命周期存在 TODO | 连接释放、优雅停机 | P1 |
| D15 | MinIO 预留但未接入，本地磁盘不适合多副本 | 扩缩容和产物持久化 | P2 |
| D16 | 缺少前端 CI、Lint/类型/覆盖率/迁移/镜像安全门禁 | 回归风险 | P1 |
| D17 | LLM 供应商、Prompt、模型版本和预算缺少统一治理 | 成本与复现性 | P1 |
| D18 | LLM 自评缺少人工校准，生成者和 Judge 可能同源 | 质量分数偏置 | P0 |
| D19 | SSE 缺少明确的断线续传协议 | 长任务用户体验 | P2 |
| D20 | 参数 `local recompute` 语义尚未真正实现 | 计算浪费、用户预期不一致 | P2 |
| D21 | 前端 Bundle 较大，沙箱运行时加载测试不稳定 | 首屏性能、测试稳定性 | P2 |
| D22 | 上传材料、下载产物和审计链缺少完整安全边界 | 数据泄露、取证困难 | P1 |

---

## 3. 优先级原则与实施总览

### 3.1 排序原则

1. **安全阻断项优先于性能优化**：只要生成代码仍与 API 同环境执行，就不应公开部署。
2. **先固定基线，再重构架构**：没有稳定测试和 Eval，无法判断重构是否造成质量回退。
3. **先统一状态机，再做并发**：在三套编排逻辑上直接并发会放大竞态和恢复问题。
4. **先接入 RAG，再跑 RAG 指标**：当前独立检索 API 不应被包装成完整 RAG。
5. **先建立数据真源，再扩展对象存储和多副本**。

### 3.2 推荐实施阶段

| 阶段 | 主题 | 建议工期 | 关键产出 | 是否阻断下一阶段 |
|---|---|---:|---|---|
| Phase 0 | 基线修复与事实对齐 | 2–3 天 | CI 全绿、文档可信、依赖基线 | 是 |
| Phase 1 | EduFlowBench v1 | 5–8 天 | 领域数据集、指标、报告、回归门禁 | 是 |
| Phase 2 | 编排统一与真正 RAG | 7–12 天 | 单一 LangGraph 主链、Retrieval、引用 | 是 |
| Phase 3 | 持久化任务与安全执行 | 7–12 天 | Worker 队列、沙箱、任务恢复 | 公开部署阻断 |
| Phase 4 | 可观测性、数据一致性与模型治理 | 6–10 天 | Trace、成本、单一真源、Prompt 版本 | 否 |
| Phase 5 | 鉴权、存储与生产部署 | 7–12 天 | RBAC、MinIO、全容器、健康检查 | 公开部署阻断 |
| Phase 6 | 性能、局部重算与作品集收尾 | 4–7 天 | 并发优化、Bundle 优化、简历数据 | 否 |

单人建议总工期约 6–9 周。若只为近期投递，优先完成 Phase 0、1、2，并至少完成 Phase 3 的安全隔离最小版本。

---

## 4. Phase 0：基线修复与事实对齐

### 4.1 目标

建立一个可信、可重复的起点。任何后续改造都必须能与该基线比较。

### 4.2 工作项

#### P0-0.1 修复前端失败测试

重点检查 `SandboxRenderer` 动态加载 Babel/Tailwind 运行时的状态机：

- 将运行时加载抽象为可注入 loader；
- 单元测试中显式 resolve/reject loader；
- 避免依赖 1 秒固定等待；
- 分别覆盖 loading、ready、compile error、runtime error；
- 确认组件卸载后不会继续 setState。

验收标准：

- `npm run verify` 连续执行 3 次全部通过；
- 不通过增加全局测试超时掩盖问题；
- 构建阶段仍正常执行。

#### P0-0.2 统一测试命令和运行环境

- 后端 CI 固定 Python 3.12；
- 为 Manim Smoke Test 配置仓库内可写临时目录；
- 区分 `unit`、`integration`、`render-smoke`、`online-eval` 标记；
- 默认 PR 不调用真实付费模型；
- Nightly 或手动工作流运行真实模型 Eval；
- 清理 AsyncMock 未 await 警告和 pytest cache 权限警告。

验收标准：

- 后端非在线测试无 warning；
- Render Smoke 在 CI Linux 环境稳定通过；
- 测试报告明确显示 passed/skipped/failed，而非只写静态数字。

#### P0-0.3 补齐前端 CI

新增前端工作流：

```text
npm ci
  → npm run typecheck
  → npm run lint
  → npm run test
  → npm run build
```

同时增加：

- Python lint/format 检查；
- Alembic `upgrade head` Smoke Test；
- OpenAPI Schema 生成检查；
- Docker image build 检查。

#### P0-0.4 锁定依赖和运行时

- Python 采用 `uv.lock` 或 `pip-tools` 生成锁文件；
- Node 统一使用 `npm ci` 和现有 `package-lock.json`；
- 固定 Python、Node、Postgres、Redis、MinIO、Manim、FFmpeg 基线版本；
- MinIO 不再使用 `latest`；
- 增加 Dependabot/Renovate，但升级必须经过测试和 Eval。

#### P0-0.5 修正文档

- 测试数量改为由 CI Badge/报告生成，避免手工维护；
- “全容器化”在加入 Web 容器前改为“后端及基础设施容器化”；
- 明确 pgvector 尚未进入 Agent 主链；
- 明确认证、对象存储、队列和沙箱现状；
- 明确 5 个 Agent 是职责节点，不夸大为自治协作平台。

### 4.3 Phase 0 完成定义

- 主分支前后端 CI 全绿；
- README 与实际部署、测试、RAG 状态一致；
- 依赖安装可复现；
- 建立 `baseline-v0.8` 测试报告，供后续阶段比较。

---

## 5. Phase 1：EduFlowBench v1

### 5.1 目标

让 Prompt、模型、检索、Reflection 和并发重构都能够被量化比较。EduFlowBench 是后续改造的质量地基。

### 5.2 建议目录

```text
agent/evals/
├── README.md
├── datasets/
│   ├── eduflowbench_v1.jsonl
│   ├── injection_cases.jsonl
│   └── retrieval_cases.jsonl
├── schemas/
│   └── case.schema.json
├── graders/
│   ├── deterministic.py
│   ├── algorithm_oracle.py
│   ├── retrieval.py
│   ├── llm_judge.py
│   └── human_calibration.py
├── runners/
│   ├── run_offline.py
│   ├── run_online.py
│   └── compare_runs.py
├── reports/
└── tests/
```

### 5.3 数据集设计

EduFlowBench v1 建议先做 50 个案例：

| 类型 | 数量 | 示例 |
|---|---:|---|
| 算法 | 15 | Dijkstra、BFS、归并排序、动态规划 |
| 数据结构 | 10 | 链表、堆、AVL、哈希冲突 |
| 操作系统 | 8 | RR 调度、死锁、分页、同步互斥 |
| 计算机网络 | 7 | TCP 握手、拥塞控制、路由 |
| 数据库/软件工程 | 5 | 索引、事务隔离、设计模式 |
| 自定义算法和材料约束 | 5 | 用户定义步骤、材料冲突、术语别名 |

每个案例至少包含：

- `case_id`、版本、领域和难度；
- 用户主题和教师约束；
- 可选材料与可信来源；
- 期望教学目标；
- 必须出现/禁止出现的知识点；
- 算法输入和参考输出；
- 状态不变量；
- 检索相关文档 ID；
- Judge Rubric；
- 是否要求 Manim 渲染。

另设不计入普通质量均值的鲁棒性集合：

- Prompt Injection；
- 空输入、极长输入、乱码；
- 错误或相互冲突的材料；
- 大规模图和数组；
- 模型超时、限流、截断、非法 JSON；
- 检索服务不可用；
- 数据库/Redis 短暂不可用。

### 5.4 指标体系

#### A. 确定性指标

- `dsl_schema_pass_rate`
- `frame_id_uniqueness_rate`
- `reference_integrity_rate`
- `state_consistency_pass_rate`
- `required_concept_coverage`
- `forbidden_claim_violation_rate`
- `prompt_injection_resistance_rate`
- `manim_validation_pass_rate`
- `manim_first_render_success_rate`

#### B. 算法可执行指标

为主要算法建立参考实现，不只检查最终答案：

- 最终输出是否与 Oracle 一致；
- 每帧状态是否能从上一帧通过合法操作得到；
- Dijkstra 已确定节点距离不得回退；
- 排序操作必须保持元素多重集合不变；
- 队列/栈操作满足 FIFO/LIFO；
- 调度时间线满足算法约束；
- 图边和节点引用必须存在。

#### C. RAG 指标

在 Phase 2 接入检索后启用：

- Recall@K、Precision@K、MRR；
- Context Precision/Recall；
- Faithfulness/Groundedness；
- 引用覆盖率和引用正确率；
- 无相关证据时的拒答或降级正确率。

#### D. LLM Judge 指标

- 教学事实正确性；
- 清晰度；
- 教学顺序合理性；
- 例子与主题一致性；
- 交互设计有效性；
- 完整性；
- 难度与受众匹配度。

Judge 规则：

- Judge 与生成模型尽量不同；
- 使用固定 Rubric 和结构化输出；
- 隐藏候选模型名称；
- 模型/Prompt 比较优先使用 Pairwise；
- 至少 20% 样本人工复核；
- 报告 Judge 与人工的一致率；
- Judge 分数不得覆盖确定性失败；
- 保存 Judge 模型、Prompt 版本和原始理由。

#### E. 工程指标

- 端到端 p50/p95/p99 延迟；
- 各节点延迟；
- 输入/输出 Token；
- 单案例估算成本；
- 结构化解析重试率；
- Reflection 触发率和平均循环数；
- Reflection 前后质量增量；
- 模块成功率和部分失败率；
- 队列等待时间与任务恢复率。

### 5.5 模型 Workbench

不优先运行与业务无关的 GAIA、AgentBench、SWE-bench。建立内部 Model Workbench，在相同数据集、Prompt、温度和预算下比较候选模型：

| 模型配置 | 质量 | 首次成功率 | p95 | 平均成本 | 结论 |
|---|---:|---:|---:|---:|---|
| Model A | 待测 | 待测 | 待测 | 待测 | Planner 候选 |
| Model B | 待测 | 待测 | 待测 | 待测 | Coder 候选 |
| Model C | 待测 | 待测 | 待测 | 待测 | Judge 候选 |

允许不同节点选择不同模型，但必须经过 EduFlowBench，而不是凭主观印象选择。

### 5.6 CI 策略

- PR：运行 10 个无付费或低成本 Smoke Eval；
- main：运行完整确定性 Eval；
- Nightly：运行真实模型 50 个案例；
- Release：运行完整模型矩阵和 Manim Render Eval；
- 保存 JSON 原始结果与 Markdown/HTML 报告；
- 与最近稳定版本比较，超过阈值则阻断发布。

初始门禁建议：

- DSL Schema 通过率不得下降；
- Prompt Injection 防御不得下降；
- 算法正确率下降超过 2 个百分点则失败；
- p95 延迟增长超过 20% 时告警；
- 单任务成本增长超过 20% 时告警；
- Manim 首次渲染成功率不得下降。

### 5.7 Phase 1 完成定义

- 至少 50 个版本化案例；
- 至少 5 类确定性 Grader；
- Judge 经人工样本校准；
- 支持两次运行对比；
- 生成第一份公开基线报告；
- CI 能检测质量、延迟和成本回归。

---

## 6. Phase 2：统一编排与真正 RAG

### 6.1 目标架构

```text
START
  ↓
Input Guard / Context Builder
  ↓
Planner
  ↓
HITL Approval ── Reject → Replan
  ↓ Approve
Query Rewrite
  ↓
Retrieve → Rerank → Context Select
  ↓
Knowledge
  ↓
Module Fan-out（受控并发）
  ├── Frames → Quality → Reflection ↺
  ├── Mindmap
  ├── Cards
  ├── Quiz
  └── Other Modules
  ↓
Aggregate / Validate
  ↓
Persist Version
  ↓
END
```

### 6.2 单一编排入口

- 删除服务层对 `knowledge_node → coder_node → quality_node → reflection_node` 的重复手动串联；
- Normal、Approve、Reject、Regenerate、Feedback、Module Retry 都使用统一 Graph Command；
- 状态迁移只在 Graph 节点/路由函数中定义；
- SSE 订阅 Graph 事件，不自行复制业务状态机；
- Checkpointer 是工作流恢复的唯一来源；
- 数据库业务表保存可查询投影，而不是另一套运行状态。

为降低一次性重构风险：

1. 先写 Characterization Tests 固定现有行为；
2. 新建 `workflow_v2` 与旧链并行；
3. 使用同一 EduFlowBench 做 Shadow Comparison；
4. 达到一致性后切换流量；
5. 删除旧手动链。

### 6.3 RAG 主链接入

新增状态字段：

```text
retrieval_query
retrieved_documents
selected_contexts
retrieval_metrics
citations
retrieval_degraded
```

实现步骤：

1. Planner 输出知识需求和检索关键词；
2. Query Rewrite 生成多个检索查询；
3. pgvector 召回候选知识；
4. 可选关键词/BM25 与向量结果融合；
5. Reranker 排序；
6. Context Selector 根据 Token 预算裁剪；
7. Knowledge/Coder 使用带 ID 的上下文；
8. DSL 中保留知识点到 source ID 的引用；
9. 无结果、低相似度、Embedding 失败时显式降级。

安全要求：

- 检索内容视为不可信数据；
- System Prompt 明确禁止执行检索文本中的指令；
- 材料和检索片段带来源、类型与信任等级；
- 用户材料不得无条件覆盖权威规则；
- 记录最终进入 Prompt 的上下文，而不是只记录召回结果。

### 6.4 模块 DAG 与受控并发

- 为生成器声明 `requires`、`produces`、`optional_requires`；
- 根据选择模块构建 DAG；
- 无依赖模块使用 `TaskGroup`/`gather` 并发；
- 使用全局和每用户 Semaphore；
- Frames 完成后才能启动依赖 Frames 的 Video；
- 单模块失败不取消无依赖模块；
- Aggregate Node 统一收敛成功、失败、警告和引用；
- 并发上限由配置控制并进入 Trace。

### 6.5 真正的局部重算

- 建立 Frame/Module 依赖图；
- 参数变更映射到受影响节点；
- 被锁定帧禁止覆盖；
- 只重算受影响帧及后继状态；
- 重算产生新 Artifact Version；
- UI 展示变更范围与旧/新版本差异。

如果短期无法实现，应将 `recompute_scope=local` 从 UI/API 能力声明中移除，避免虚假语义。

### 6.6 Phase 2 完成定义

- 所有生成入口共用一张 LangGraph；
- 中断后可在进程重启后继续；
- pgvector 检索进入实际生成链并产生引用；
- 具备检索降级路径；
- 独立模块并发执行且有上限；
- workflow_v2 在 EduFlowBench 上不低于旧链质量，p95 有明确改善。

---

## 7. Phase 3：持久化任务队列与生成代码安全

### 7.1 任务系统

统一承载以下任务：

- 视频导出；
- Feedback Reflection；
- 大型模块生成；
- 材料解析；
- Nightly Eval；
- Embedding 批量生成。

推荐复用 Redis，引入 Celery、RQ 或 Dramatiq。选择标准不是框架流行度，而是：

- 支持重试和退避；
- 支持任务超时和取消；
- 支持 Worker 心跳；
- 易于为每个任务创建隔离执行环境；
- 状态能够同步到 PostgreSQL。

### 7.2 任务状态机

```text
created → queued → leased → running → succeeded
                         ├→ retry_wait → queued
                         ├→ failed
                         ├→ cancelled
                         └→ timed_out
```

要求：

- API 创建任务时生成 idempotency key；
- PostgreSQL 为任务最终状态真源；
- Redis 只承担队列和短期进度；
- Worker 使用 lease，超时后任务可被重新领取；
- 重试必须区分可重试和不可重试错误；
- 每次 attempt 独立记录日志和产物；
- 进程退出时停止领取新任务并等待当前任务达到安全点；
- 状态更新使用乐观锁，避免旧 Worker 覆盖新 attempt。

### 7.3 Manim 安全沙箱

最低安全基线：

- 独立 Worker/临时容器，不与 API 共进程；
- 非 root 用户；
- `read_only` 根文件系统；
- 独立只写任务目录；
- 默认禁用网络；
- CPU、内存、磁盘、PID、文件数和执行时间限制；
- 禁止挂载 Docker Socket、宿主源码和凭证；
- 仅向 Worker 提供 DSL、渲染配置和一次性任务 ID；
- 不向渲染容器提供数据库、Redis、LLM API Key；
- 任务完成后验证 MP4/SRT/JSON 文件类型、大小和路径；
- 超时强制终止整个进程组；
- 保留脱敏后的失败脚本用于复现。

静态 Validator 继续保留，但定位为“提高成功率和提前失败”，而不是安全边界。

### 7.4 下载和路径安全

- 下载必须按 artifact ID 查询，不接受任意文件路径；
- 对解析后的路径执行根目录包含关系检查；
- 限制 Content-Disposition 文件名；
- 上传文件进行 MIME、扩展名、Magic Bytes 和大小四重校验；
- PDF/PPT 解析也放入受限 Worker；
- 记录上传者、解析任务和下载审计事件。

### 7.5 Phase 3 完成定义

- API 重启不会丢失已接受任务；
- 同一幂等键不会产生重复视频；
- Worker 崩溃后任务能够恢复或明确失败；
- 生成代码无法访问外网、宿主源码和服务凭证；
- 压测下 API 不被 Manim CPU/内存拖垮；
- 安全测试包含恶意 import、文件读取、网络访问、fork bomb 和超大产物。

---

## 8. Phase 4：可观测性、模型治理与数据一致性

### 8.1 工作流 Trace

统一关联 ID：

```text
request_id
  └── workflow_run_id
       └── node_run_id
            └── llm_call_id / task_attempt_id
```

每个节点记录：

- 开始/结束时间和状态；
- 模型、Endpoint、Prompt Version；
- 输入/输出 Token 和估算成本；
- 重试次数和失败分类；
- 结构化解析是否成功；
- 检索文档 ID、分数和上下文长度；
- Reflection 前后 Artifact Version；
- 缓存命中；
- 不记录 API Key、完整敏感材料和未经脱敏的用户数据。

### 8.2 Metrics 与告警

最小指标：

- API QPS、错误率、p95；
- Workflow 成功率和各节点错误率；
- LLM p95、429、timeout、parse retry；
- Token/成本按模型、节点、用户聚合；
- 队列深度、等待时间、活跃 Worker；
- Manim 成功率、渲染耗时、超时率；
- RAG 召回数、低置信降级率；
- Reflection 触发率和改善率；
- SSE 活跃连接和断连率。

推荐 OpenTelemetry 作为统一埋点协议，Prometheus/Grafana 负责指标，日志平台负责检索。是否接入 LangSmith 可作为可选实现，不应让核心 Trace 数据只能存在于第三方平台。

### 8.3 LLM Gateway

将散落的模型调用收敛到统一网关：

- 节点级模型路由；
- timeout、retry、指数退避和 jitter；
- 429/5xx 错误分类；
- Circuit Breaker；
- 并发与速率限制；
- Token Budget；
- 最大成本保护；
- Provider fallback；
- Prompt 模板版本；
- 缓存策略；
- 统一使用量事件。

注意：结构化 JSON 截断可以重试，但不得简单无限加倍 `max_tokens`。应设置节点硬预算，并在超出预算时采用分段生成或明确失败。

### 8.4 数据单一真源

推荐采用“不可变 Artifact Version + 查询投影”方案：

- `project_versions.dsl_snapshot` 保存不可变完整产物；
- `projects.current_version_id` 指向当前版本；
- `frames` 表作为当前版本的查询/编辑投影；
- `module_outputs` 不再复制完整 Frames，只保存 artifact reference；
- 编辑帧时基于 `base_version` 创建新版本；
- 使用 `revision` 乐观锁防止覆盖；
- 导出任务固定绑定 `source_artifact_version`；
- 恢复历史版本不原地修改旧版本；
- 增加一致性校验和修复脚本。

迁移步骤：

1. 新增版本引用字段和约束；
2. 双写一段时间并统计差异；
3. 读路径切换到新真源；
4. 停止旧字段写入；
5. 数据核对后再清理旧副本。

### 8.5 SSE 可靠性

- 所有事件包含单调递增 `event_id`；
- 客户端使用 `Last-Event-ID` 重连；
- 服务端从持久化事件或任务状态恢复；
- 心跳事件与业务进度分离；
- Done/Error 为终态且只能发一次；
- 前端刷新后能够恢复当前任务，而不是重新启动生成。

### 8.6 Phase 4 完成定义

- 任一失败请求可由 workflow_run_id 定位到具体节点和调用；
- 能展示按模型、节点统计的成本和 p95；
- Prompt/模型变更可复现；
- DSL/Frames/Module Outputs 不再发生静默漂移；
- SSE 断开后可以续传。

---

## 9. Phase 5：鉴权、对象存储与生产部署

### 9.1 鉴权与授权

最低范围：

- 后端 User/Session 模型；
- 密码使用 Argon2/bcrypt，或接入 OAuth/OIDC；
- HttpOnly、Secure、SameSite Cookie；
- `/auth/me` 和登出/失效机制；
- 所有 Project、Frame、Material、Version、Export 查询验证 owner；
- 教师/学生/管理员基础角色；
- 创建任务、上传、下载和导出的限流与配额；
- 关键操作审计日志；
- 删除项目同时处理任务、版本和对象存储引用。

安全测试：

- 跨用户访问项目；
- 枚举 UUID；
- 越权下载产物；
- 重放导出请求；
- CSRF/CORS；
- Session 过期；
- 日志和错误响应不泄露凭证。

### 9.2 MinIO/S3 接入

抽象 `ArtifactStore`：

```text
put / get / delete / exists / signed_url / metadata
```

实现：

- LocalArtifactStore：开发和单元测试；
- S3ArtifactStore：生产环境；
- 数据库只保存 object key、hash、size、content type；
- 下载使用短期签名 URL 或授权代理；
- 上传和渲染完成后计算 SHA-256；
- 设置生命周期策略清理临时和失败产物；
- 迁移脚本处理已有本地文件。

### 9.3 完整容器化

Compose 至少包含：

- Web/Nginx；
- Agent API；
- Task Worker；
- Sandbox Render Worker；
- PostgreSQL/pgvector；
- Redis；
- MinIO。

要求：

- 镜像固定版本；
- 多阶段构建；
- 非 root；
- Secret 不写入镜像；
- API 和 Worker 分别扩缩容；
- 数据服务不默认暴露公网端口；
- 提供 `.env.example`，生产密码无默认 `changeme`；
- Alembic 迁移采用单独 Job，避免多个 API 副本同时迁移。

### 9.4 健康检查和生命周期

端点拆分：

- `/health/live`：进程存活，不访问外部依赖；
- `/health/ready`：检查 DB、Redis、对象存储和必要配置；
- `/health/startup`：迁移和初始化是否完成。

同时：

- FastAPI lifespan 初始化并关闭 DB、Redis、HTTP/LLM Client；
- Worker 支持 graceful shutdown；
- readiness 失败时停止接收新流量；
- 不因可选服务不可用把整个 API 判死，例如 MinIO 可按功能开关处理。

### 9.5 Phase 5 完成定义

- 两个用户无法访问彼此项目和产物；
- API/Worker 多副本共享对象存储；
- `docker compose up` 能真正启动前端和完整后端；
- Readiness 能识别依赖故障；
- 文档中的部署步骤由 CI 实际验证。

---

## 10. Phase 6：性能优化与作品集收尾

### 10.1 后端性能

- 基于 Trace 找最长节点，不凭感觉优化；
- Planner 与 Retrieval 中可并行部分并行；
- 无依赖模块 fan-out；
- 对相同知识点和 Prompt Version 做安全缓存；
- 长 DSL 使用分阶段/分章节生成，避免单次 32K–64K 输出；
- 流式输出细化为真实阶段，不伪造线性百分比；
- 设置用户级和全局并发上限；
- 为数据库常用查询添加索引和 EXPLAIN 基线。

### 10.2 前端性能

- 路由级代码分割；
- Babel、交互沙箱、KaTeX、React Flow 按需加载；
- Sandbox Runtime 预加载但不进入首屏主包；
- 分析重复依赖；
- 设置 Bundle Budget；
- 大型成果列表虚拟化；
- 修复运行时 loader 的错误恢复和缓存。

初始 Bundle 门禁建议：

- 主入口 gzip 不超过 250 KB；
- Babel/沙箱独立异步 Chunk；
- Landing Page 不加载工作台运行时；
- CI 对 Chunk 增长超过 15% 发出告警。

### 10.3 产品闭环

- “全部失败模块重试”；
- 任务取消；
- 重试前展示预计成本；
- 参数局部重算差异预览；
- 质量报告展示确定性错误与 Judge 建议的区别；
- 引用可展开查看原始知识片段；
- 导出明确绑定 Artifact Version；
- 管理页展示任务、成本和 Eval 趋势。

### 10.4 作品集产出

仓库应新增：

- 一张当前架构图和一张目标架构图；
- 一份 ADR：为什么选择 DSL；
- 一份 ADR：为什么统一到 LangGraph；
- 一份 ADR：生成代码的威胁模型与隔离方案；
- EduFlowBench 数据说明和基线报告；
- 失败案例分析；
- 3 分钟演示视频；
- 可复现部署命令；
- 性能、质量、成本对比表。

---

## 11. 跨阶段测试计划

### 11.1 测试金字塔

| 层级 | 内容 | 是否调用真实模型 |
|---|---|---|
| Unit | Schema、路由、状态转换、Grader、权限 | 否 |
| Contract | LLM Provider、Queue、S3、SSE、OpenAPI | 默认否 |
| Integration | Graph + DB + Redis + Worker | 使用 Fake LLM |
| E2E | Browser → API → Graph → Artifact | 可分离在线/离线 |
| Eval | 真实模型质量、成本、延迟 | 是 |
| Security | Sandbox、越权、注入、路径穿越 | 部分 |
| Load | API、SSE、队列、Worker 容量 | 可使用 Fake LLM |

### 11.2 必须新增的故障注入

- LLM 429、500、timeout、空响应、截断 JSON；
- Embedding 失败；
- pgvector 无结果和连接断开；
- Redis 重启；
- Worker 在任务中途崩溃；
- API 在 HITL 等待期间重启；
- SSE 断开并重连；
- 数据库提交前后失败；
- 对象存储上传成功但 DB 提交失败，及反向情况；
- Manim 超时、OOM、恶意脚本和超大输出；
- 并发编辑同一 Artifact Version。

---

## 12. 数据库与 API 迁移原则

- 所有 Schema 变化通过 Alembic；
- 迁移必须可在一份生产规模样本数据上演练；
- 大字段迁移采用 expand → migrate → contract；
- 新旧 API 至少保留一个版本的兼容期；
- SSE 事件增加 `schema_version`；
- Artifact、Workflow、Task 都使用明确版本号；
- 破坏性迁移前生成备份和一致性报告；
- `db/init.sql` 只负责必要扩展初始化，业务表结构以 Alembic 为唯一来源。

---

## 13. 安全与隐私检查表

- [ ] `.env`、API Key、数据库密码未进入 Git 和镜像层。
- [ ] Prompt、Trace 和失败脚本经过敏感信息脱敏。
- [ ] 用户材料具有保留期限和删除能力。
- [ ] 所有资源查询校验 owner/role。
- [ ] 上传、解析、生成代码、下载均具有独立威胁模型。
- [ ] 沙箱无网络、无宿主凭证、无 Docker Socket。
- [ ] API 有速率、并发、Token 和成本限制。
- [ ] Prompt Injection 测试同时覆盖用户输入、上传材料和检索文档。
- [ ] 审计日志不可被普通用户修改。
- [ ] 错误响应不包含 Traceback、路径、Prompt 或凭证。

---

## 14. 推荐 Issue/Epic 拆分

### Epic A：可信基线

- A1 SandboxRenderer 稳定测试
- A2 Frontend CI
- A3 Backend warning cleanup
- A4 Dependency lock
- A5 README/DEPLOY 事实对齐

### Epic B：EduFlowBench

- B1 Case Schema 与 50 个案例
- B2 Deterministic Graders
- B3 Algorithm Oracles
- B4 LLM Judge 与人工校准
- B5 Report/Compare CLI
- B6 Eval CI/Nightly

### Epic C：Workflow v2

- C1 Characterization Tests
- C2 Unified State/Command
- C3 HITL Resume
- C4 Module DAG
- C5 Feedback/Regenerate 统一
- C6 旧链删除

### Epic D：RAG

- D1 Query Rewrite
- D2 Hybrid Retrieve/Rerank
- D3 Context Budget
- D4 Citation Schema/UI
- D5 Retrieval Eval
- D6 Injection Guard

### Epic E：Task Platform 与 Sandbox

- E1 Persistent Job Schema
- E2 Queue Worker
- E3 Retry/Lease/Idempotency
- E4 Manim Sandbox
- E5 Material Parse Sandbox
- E6 Task Recovery/Load Test

### Epic F：Observability 与治理

- F1 OpenTelemetry Trace
- F2 Metrics Dashboard
- F3 LLM Gateway
- F4 Prompt Registry
- F5 Cost Budget/Alert
- F6 SSE Resume

### Epic G：数据、权限和部署

- G1 Artifact 单一真源
- G2 Optimistic Lock
- G3 Auth/Session/RBAC
- G4 ArtifactStore/MinIO
- G5 Full Compose
- G6 Health/Lifecycle

### Epic H：性能和作品集

- H1 Backend concurrency tuning
- H2 Local recompute
- H3 Frontend code splitting
- H4 Architecture/ADR
- H5 Benchmark report/demo
- H6 Resume metrics

---

## 15. 里程碑验收表

| 里程碑 | 必须满足的结果 |
|---|---|
| M0 可信仓库 | 前后端 CI 全绿；依赖锁定；README 与事实一致 |
| M1 可评估 Agent | EduFlowBench ≥50 例；确定性+Judge；有基线报告 |
| M2 真正 RAG Workflow | 单一 Graph；检索入链；引用可追踪；并发受控 |
| M3 可恢复且安全 | 队列持久化；重启恢复；生成代码隔离；安全测试通过 |
| M4 可运营 | Trace、成本、指标、告警、Prompt/模型版本化 |
| M5 可公开部署 | Auth/RBAC、MinIO、完整 Compose、Readiness |
| M6 简历就绪 | 指标稳定、文档完整、演示视频、可复现部署 |

---

## 16. 最小投递版本与完整版本

### 16.1 最小投递版本

时间有限时必须完成：

1. Phase 0 全部；
2. EduFlowBench 30–50 个案例；
3. 确定性正确性评测与一次模型对比；
4. pgvector 接入主链并带引用；
5. 统一正常生成与 HITL 恢复路径；
6. Manim 至少迁移到无网络、无凭证的独立 Worker；
7. 一份真实 Benchmark 报告。

此时可以投递 Agent 应用开发、LLM 应用工程、RAG/Workflow 方向岗位。

### 16.2 完整工程版本

在最小版本上继续完成：

- 持久化任务与 Worker 恢复；
- 全链路 Trace 和成本治理；
- 数据单一真源；
- 鉴权与多租户；
- MinIO 和完整容器化；
- 局部重算与性能优化。

此时可以更有底气投递强调生产系统、平台工程和 Agent Infra 的岗位。

---

## 17. 简历数据收集模板

每个 Release 自动产出以下表格，禁止在简历中填写未经测试的数字：

| 指标 | Baseline | Current | 变化 |
|---|---:|---:|---:|
| DSL Schema 通过率 | 待测 | 待测 | 待测 |
| 算法正确率 | 待测 | 待测 | 待测 |
| 状态一致性通过率 | 待测 | 待测 | 待测 |
| Reflection 后正确率 | 待测 | 待测 | 待测 |
| Manim 首次渲染成功率 | 待测 | 待测 | 待测 |
| 端到端 p95 | 待测 | 待测 | 待测 |
| 平均 Token | 待测 | 待测 | 待测 |
| 平均成本 | 待测 | 待测 | 待测 |
| 模块全部成功率 | 待测 | 待测 | 待测 |
| Prompt Injection 防御率 | 待测 | 待测 | 待测 |
| 任务重启恢复率 | 待测 | 待测 | 待测 |

推荐最终简历表达：

> 构建覆盖 N 个计算机科学主题的 EduFlowBench，结合参考算法执行、DSL 状态不变量、渲染 Smoke Test 与经人工校准的 LLM Judge，对 Agent 的正确性、可渲染性、延迟和成本进行持续回归；通过 RAG、工作流统一和 Reflection 优化，将 X 指标从 A 提升至 B。

---

## 18. 明确暂不优先的事项

以下事项在核心缺陷完成前不应占用主要时间：

- 增加更多成果模块；
- 为了宣传数字运行不匹配的 GAIA、AgentBench、SWE-bench；
- 复杂的多 Agent 自由对话或自治委派；
- 大规模更换前端设计系统；
- 未经 Eval 证明有效的模型微调；
- 在没有真实容量数据前引入 Kubernetes；
- 同时支持过多 LLM Provider。

只有当 EduFlow 的产品范围扩展到通用浏览、开放环境工具调用或代码修复 Agent 时，才有必要选择对应公开 Benchmark。

---

## 19. 执行纪律

每个改造 PR 必须回答：

1. 它解决了哪个缺陷编号？
2. 是否改变 Workflow、Prompt、模型、DSL 或数据 Schema？
3. 使用什么测试和 Eval 证明没有回归？
4. 对延迟、Token、成本和安全有什么影响？
5. 是否需要迁移、回滚或 Feature Flag？
6. 文档和架构图是否同步？

任何涉及 Prompt、模型、检索或工作流的变更，没有 EduFlowBench 对比结果不得直接发布；任何涉及生成代码执行的变更，没有沙箱安全测试不得公开部署。

