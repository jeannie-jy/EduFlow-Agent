# EduFlow-Agent 工程化改造与 EduFlowBench 实施计划

> 文档状态：Draft v1.0  
> 制定日期：2026-09-03  
> 适用版本：EduFlow-Agent v0.9.x
> 核心目标：在不继续扩张功能面的前提下，补齐评测、可靠性、安全、可观测性和可复现交付能力。

---

## 1. 改造目标与完成标准

### 实施进度（2026-09-06）

- Phase 0 已完成：前后端 CI、Python 3.12 锁文件、生命周期关闭、文档事实对齐；
  当前复验结果为前端 41 files / 297 tests，后端常规测试 1107 passed、6 deselected；
  真实 Manim 渲染由独立 CI job 执行，在线评测仍需显式授权。
- Phase 1 基础设施已完成：50 个核心案例、8 个注入案例、10 个检索案例，确定性
  grader、检索指标、在线 opt-in runner、Judge 契约、人工校准与回归比较器已落地。
  核心 50 例已通过一方 `live_workflow` 适配器接入生产 LangGraph，并提供凭据门控的手动 CI；
  独立 `live_judge` 使用分离的 endpoint/key/model 做七维盲评，确定性失败不可被覆盖，候选与
  Judge Token/成本分开记录。runner 在总成本达到阈值后停止启动新案例/Judge。首次真实模型
  质量基线仍需凭据、成本授权和至少 20% 人工复核，未伪造分数。
- Phase 2 主动执行路径已统一：正常生成、HITL `Command(resume=...)` 和局部重生成
  共用一张支持多入口的 LangGraph，模块 DAG 作为 Knowledge 后的图节点；pgvector
  证据携带 source ID、不可信边界和降级状态，检索含多查询、RRF 与 context budget。
  绕过 Graph 的旧版 resume/regenerate/module 私有实现已删除；模块 DAG 的 start/done/error
  细粒度事件通过 LangGraph custom event 通道透传到统一 SSE 协议。
  手动重生成已实现 `single_frame`、`frame_range`、`from_frame` 与 `all_frames` 的确定性
  范围合并、稳定 Frame ID 和锁定帧保护；参数重算会先校验键、类型与约束，纯 `local`
  变更不调用模型；结构性参数通过显式 DSL 依赖和结构化引用推断，重算最早受影响帧及其
  状态后继，缺少证据时安全降级全量。执行前 UI 展示影响范围并以内容指纹防止过期预览写入，
  版本历史也可展示 Frame/Parameter/Metadata 结构化差异后再确认恢复。参数影响现已沿生成器
  `requires` DAG 传播到下游产物，预览会显示受影响模块并将其标记过期，成功重生成后清除标记。
  成果页可将全部失败模块作为一个持久化批次交回同一 DAG 重试，并连接 API 返回的唯一
  SSE stream，避免多个单模块请求并发覆盖项目快照；单模块连接失败也会正确结束运行态。
  真实 Tool Calling 已进入 Knowledge 主链：统一
  `ToolSpec`/Registry 只暴露 `knowledge_search`、`material_lookup`、`get_project_context`，
  模型可在有界多轮中自主选择 0–N 个工具，执行结果以标准 ToolResult 消息回填。
  Pydantic Schema、服务端 actor/project/request/workflow/node 上下文、owner 二次校验、
  超时/轮数/调用数/进程级共享并发/结果大小预算、提示注入边界和持久化脱敏 Tool Trace 已落地；
  EduFlowBench 新增 16 个 Tool Calling 案例及确定性 grader。真实模型工具选择基线仍待授权运行。
- Phase 3 已落地最小可恢复链路：API 仅持久化排队，独立非 root 准备器使用数据库
  lease 领取和有限重试，再将已校验脚本及其 SHA-256 经共享任务目录交给无网络、无服务凭据的
  Manim 沙箱；沙箱执行前复核摘要并拒绝审批后篡改。Compose 默认关闭并通过 `video` profile
  显式启用。排队接口已有幂等键、
  有限重试、逐次 attempt 记录、lease 心跳、owner 隔离的取消接口及超时进程组回收；
  取消或 lease 丢失会停止准备器，迟到结果不能覆盖终态。失败任务按 attempt 执行带 jitter
  的指数退避，并区分可重试/不可重试错误；渲染进程运行期间执行每任务总字节和文件数配额，
  超限会终止进程组且不再重试。教师反馈也已改为数据库持久化后台任务，由独立
  `task-worker` 通过 lease、heartbeat、attempt 和退避重试执行统一 LangGraph Reflection，
  成功后原子写回 Frames 真源与版本。材料解析也已复用同一持久化任务系统：API 仅幂等
  入队，带凭据 Worker 从对象存储下载并签署文件，再交给无网络/无凭据、受资源约束的
  `material-sandbox` 验签解析；结果经 Schema 和大小校验后在 lease 所有权检查下原子写回。取消、
  失败重试和重启恢复沿用统一状态机。常驻沙箱仍需补齐更完整的恶意样本和压力验证。
  新建导出任务会先把 Frames 真源固化为不可变 `ProjectVersion` 并保存版本外键，Worker 只渲染
  该任务绑定的快照；项目在排队或重试期间继续编辑不会改变导出输入，旧任务保留兼容读取路径。
- Phase 5 部分完成：Web 生产容器、反向代理、liveness/readiness、Redis healthcheck 已补齐；
  后端已加入 scrypt 密码散列、HttpOnly opaque session、Redis 优先登录/注册限流、
  统一生产认证门禁、student/teacher/admin RBAC，以及项目、素材、导出 owner 隔离。
  高风险写操作仅 teacher/admin 可用，admin 可跨 owner 管理。生产认证模式已对普通写操作与
  生成/重算等高成本入口设置 Redis 优先的独立固定窗口限流，并在 Redis 故障时有界降级。
  素材具有内容签名检查，并对 PPTX 归档限制成员数、总解压体积、压缩比、加密成员和路径穿越；素材还具备保留期
  清理与删除能力；账号、项目、素材和导出关键写操作已记录 append-only audit event
  并关联 request ID。导出产物已通过 `ArtifactStore` 接入 MinIO，记录 object key、
  SHA-256、大小和 content type，并由 owner 校验后的短期签名 URL 下载；readiness 也会
  检查当前存储后端。新上传素材也已对象化，解析按需下载到隔离临时目录，生成链路只消费
  数据库中已持久化的解析结果。管理员审计查询已提供有界 cursor 分页、精确过滤、输出脱敏和
  专用查询索引，即使开发环境关闭普通认证也必须持有 admin 会话。管理员用户页现可分页/筛选账号、
  调整角色和启停状态、撤销全部会话；服务端在权限变化后强制失效旧会话，阻止自我降权和移除最后一名
  有效管理员，并提供仅在尚无管理员时可用的审计化 bootstrap 命令。存量 owner 与本地素材现有
  dry-run 优先、路径/存在性/大小预检、保留源文件且写审计的显式迁移命令；实际部署数据仍需运维
  选择接收 owner 后执行。审计归档现支持 oldest-first 有界批次、逐事件 SHA-256 hash chain、
  独立 HMAC manifest、ArtifactStore 回读验证，以及验证成功后按精确 ID 清理；默认只 dry-run，
  运维仍需设置独立 HMAC 密钥并为对象前缀启用 Object Lock/版本控制。MinIO 目前完成契约测试
  与 Compose 静态校验，真实容器集成测试待补。
  Compose 已移除数据库/MinIO 隐式默认口令，数据服务和 API 默认仅绑定回环地址；后端镜像
  已拆分 builder/runtime 阶段，运行层不再携带编译工具链。
- Phase 4/6 部分完成：Request ID 已贯穿 LLM 调用日志；统一 LLM Gateway 已覆盖 Chat
  与 Embedding 的超时、错误分类重试、指数退避+jitter、并发上限和 provider 熔断。
  Prompt 以内容指纹标识而不记录原文，进程指标包含按模型/操作的调用量、Token、估算
  成本、重试原因、平均耗时与 p95。Provider fallback、按节点模型路由和一次工作流共享的
  Token/成本硬预算已经接入；活动 DSL 读取统一以 Frames 表为真源，ProjectVersion 保存不可变
  聚合快照，`current_version_id` 在项目行锁下原子推进；帧/结构参数编辑进入 dirty working copy，
  生成、Reflection、模块产出、本地参数变更和恢复会建立或切换明确版本。
  `module_outputs.frames` 已停止重复保存完整帧数组，改为绑定当前不可变 ProjectVersion 的
  artifact reference；Alembic 0020 会归一化存量版本和非 dirty 活动快照，读取路径按需水合旧 API 投影。
  `python -m scripts.audit_artifact_consistency` 默认只读核对版本指针、快照与 Frames 投影，并可
  通过显式 `--repair-references` 仅修复引用；内容漂移只报告、不自动覆盖。
  页面级懒加载把主入口
  JS 从 1,342.14 kB 降至 547.38 kB（-59.2%）。持久化
  主生成链的持久化 workflow/node trace 已接入 PostgreSQL，可按 owner 查询 request、节点、
  模型、脱敏 Endpoint、Prompt 指纹、Token、成本、重试、耗时、结构化解析与检索摘要；不保存
  Prompt 和材料原文。反馈 Reflection Worker 已复用同一 Graph Trace；Tool Call Trace 记录工具
  版本、脱敏参数/结果摘要、状态和耗时。API/SSE 进程指标与 PostgreSQL 24 小时跨进程聚合已
  暴露为 JSON/Prometheus，Compose `observability` profile 预置 Prometheus、3 条告警和 Grafana
  运营面板；OpenTelemetry Collector、通知渠道与长期指标仓库仍待完成。
  前端生产构建已加入 gzip Bundle Budget：主入口 250 KiB、ProjectWorkspace 220 KiB、
  独立 Babel 沙箱运行时 650 KiB，任一超限或异步 chunk 消失都会使 CI build 失败。

本段只记录已验证事实；其余条目仍按下文优先级继续实施。

SSE 已加入单调事件 ID、`schema_version`、`Last-Event-ID` 重连、重复过滤、标准多行
解析和单终态约束。每次运行具有独立 stream ID，事件发送前持久化到 PostgreSQL；
可续租 producer lease 防止多连接重复执行，断连释放、进程崩溃超时接管，终态只重放。
同标签页刷新会从 sessionStorage 恢复安全 stream URL 与事件游标；本地游标缺失时，前端会经
owner 校验的活动流查询入口从 PostgreSQL SSE 账本发现并续传当前项目流，等待审批也能从项目
状态恢复。非主 Graph 模块接管时的细粒度 checkpoint 尚待完成。

依赖故障验收已新增可执行脚本与手动 CI，可真实停止 Redis、PostgreSQL、MinIO 并验证
liveness/readiness/恢复；真实 Tool Calling 也新增 8 例在线数据集、生产 Runtime 适配器和
凭证门控手动 CI。两者因本机 Docker daemon、模型凭据和成本授权不可用，当前只计“入口完成”，
不计“真实报告通过”。

工程文档已补齐 RenderScript、统一 LangGraph、执行隔离、受控 Tool Runtime、持久化执行/SSE
五份 ADR 及总体架构图；其中 Tool ADR 明确记录 MCP/Skill 未实现，避免把进程内 Registry
包装成 MCP。

按本计划全部验收项计算的当前完成度约为 **99%**。剩余顺序为：实际运行故障/容量压力测试 →
真实 Benchmark 和人工校准 → 发布材料收尾。仓库内可离线完成的工程项已收口；取得可用 Docker
daemon、模型/Judge 凭据与成本授权、Manim 环境和人工评审后，预计还需 **1–3 个集中工作日**，
其中容器故障/容量实测约 0.5–1 天、在线质量与 Tool Bench 约 0.5–1 天、人工复核约 1–2 天。

本轮改造不以增加第 11、12 个成果模块为目标，而是把已有能力从“功能可演示”提升到“结果可度量、流程可恢复、问题可追踪、执行可隔离、部署可复现”。

最终应满足以下六个结果：

1. **可评估**：建立 EduFlowBench，能够比较 Prompt、模型、检索和工作流版本，阻止质量回归。
2. **可恢复**：所有长任务具有持久化状态、幂等执行、失败重试和进程重启恢复能力。
3. **可解释**：一次生成能够追踪经过的节点、检索证据、Token、成本、耗时、重试与质量变化。
4. **可安全部署**：LLM 生成代码不在 API 进程内直接执行，项目、文件和任务具备用户级权限边界。
5. **可复现交付**：依赖锁定，前后端 CI 全绿，容器与文档一致，部署具有 readiness/liveness 检查。
6. **真实工具使用**：模型能够在受控循环中自主选择、调用并消费真实工具结果，工具调用具备 Schema、权限、预算、Trace 和 Eval 约束。

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

- 后端最近一次常规离线基线为 **1107 passed、6 deselected**；真实 Manim
  渲染用例和在线评测按独立标记及工作流运行。
- 前端最新结果为 **41 files / 297 tests 全绿**，TypeScript 与生产构建通过；
  Hook dependency 警告已清零，Lint 仍报告组件与共享导出同文件的既有 Fast Refresh 警告，
  未作为零警告宣称。
- 页面级拆包后主入口 JS 由约 1.34 MB 降至 547.38 kB；约 2.30 MB Babel Chunk
  已隔离为按需加载，后续仍应迁移到服务端预编译或更轻运行时。
- GitHub Actions 已具备前端与后端独立 CI；后端另含迁移、镜像构建和真实渲染冒烟 Job。

### 2.3 缺陷清单

| 编号 | 缺陷 | 影响 | 优先级 |
|---|---|---|---|
| D01 | 已完成：前端全量测试、类型检查、生产构建和 Bundle Budget 均为 CI 门禁 | 项目可信度、CI | 已关闭 |
| D02 | 已完成最小安全边界：API 只准备任务，生成脚本在无网络、无凭据、只读根文件系统的独立沙箱执行 | 远程代码执行、资源滥用 | 主体关闭，待压力实测 |
| D03 | EduFlowBench 数据、grader、比较器、生产 LangGraph 适配器、运行期成本闸门和手动在线 CI 已完成；真实模型质量基线待授权 | Agent 能力可复现评测，尚无真实模型报告 | 收尾：真实 Bench |
| D04 | 已完成：生成、HITL、反馈、局部重生成及单/批模块重试统一到多入口 LangGraph；模块结果由 Graph 单次落库 | 状态漂移、重复版本、维护成本 | 已关闭 |
| D05 | 已完成：pgvector 多查询/RRF 检索进入 Knowledge 主链并保留引用与降级状态 | 不能形成真实 RAG 闭环 | 已关闭 |
| D06 | 已完成：模块依赖 DAG、受控并发及失败隔离 | 时延高、资源不可控 | 已关闭 |
| D07 | 已完成：视频、反馈与材料解析使用 PostgreSQL 持久化 lease Worker | 重启丢任务、无法可靠重试 | 已关闭 |
| D08 | 已完成主体：工作流/节点/LLM/Tool Trace、成本和运营指标已持久化 | 难定位、难优化 | 主体关闭 |
| D09 | 已完成 Frames 活动真源、不可变聚合 ProjectVersion、原子 current_version 指针、dirty working copy、模块/Reflection 版本化、导出版本绑定及 module_outputs 引用化/存量迁移 | 消除静默漂移与帧数组重复存储 | 已关闭 |
| D10 | 已完成后端会话、RBAC、owner 隔离、admin 审计查询、用户/角色/会话管理 UI、安全 bootstrap、强制会话失效，以及 owner/本地素材显式迁移工具；待具体部署选择 owner 后执行 dry-run/apply | 数据越权、无法多租户部署 | 工程实现关闭，待部署操作 |
| D11 | 已完成：Python 生产/CI 锁文件与 Postgres、Redis、MinIO 镜像版本固定 | 构建不可复现 | 已关闭 |
| D12 | 已完成：Compose 包含 Web/Nginx、API、Worker、沙箱和基础设施 | 文档与交付不一致 | 已关闭，待真实启动报告 |
| D13 | 已完成：liveness 与 DB/Redis/ArtifactStore readiness 分离 | 编排系统无法判断就绪 | 已关闭，已补故障脚本 |
| D14 | 已完成：lifespan 关闭 DB、Redis、LLM/HTTP 资源，Worker 处理退出信号 | 连接释放、优雅停机 | 已关闭 |
| D15 | 已完成主体：MinIO ArtifactStore 接入素材与导出、签名下载及 DB 失败补偿 | 扩缩容和产物持久化 | 主体关闭，待多副本实测 |
| D16 | 已完成前后端 CI、类型/测试/构建、迁移和镜像构建门禁；依赖漏洞扫描可继续加强 | 回归风险 | 主体关闭 |
| D17 | 已完成主体：LLM Gateway 统一路由、重试/熔断/fallback、版本 Trace 与 Token/成本预算 | 成本与复现性 | 主体关闭，待真实成本基线 |
| D18 | 已提供独立 Judge 配置/盲评/输入隔离、确定性 20% 抽样、匿名评审表和逐维校准报告；尚未真实完成人工标注 | 评审流程可执行，校准结论仍缺外部评审 | P0 外部验收 |
| D19 | 已完成 SSE 协议、事件账本、producer lease、跨进程重放、刷新恢复及 owner 隔离的跨设备活动流发现 | 非主 Graph 模块接管仍可细化 | 主体关闭 |
| D20 | 已完成参数到 Frame 的显式/推断依赖、状态后继传播、影响预览、过期指纹及 Module DAG 下游传播 | 跨产物影响可解释，自动重生成策略仍可细化 | 主体关闭 |
| D21 | 已完成主体：路由懒加载、Babel 独立异步 Chunk、加载态测试和 gzip Bundle Budget | 首屏性能、测试稳定性 | 主体关闭 |
| D22 | 已完成上传签名/ZIP 炸弹限制、owner 下载、对象存储、材料解析沙箱、跨存储补偿、关键写审计，以及 hash-chain + HMAC、回读验证后精确清理的审计归档命令 | 数据泄露、取证困难 | 工程实现关闭，待部署 Object Lock |
| D23 | 已完成真实 Tool Calling Runtime、3 个只读工具、上下文/权限/预算、Trace 与 16 例 Eval；尚未运行真实模型选择基线 | 代码闭环可验证，模型效果尚无真实报告 | P1 收尾：真实 Bench |

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
| Phase 2 | 编排统一、真正 RAG 与 Tool Calling | 9–15 天 | 单一 LangGraph、Retrieval、受控工具循环 | 是 |
| Phase 3 | 持久化任务与安全执行 | 7–12 天 | Worker 队列、沙箱、任务恢复 | 公开部署阻断 |
| Phase 4 | 可观测性、数据一致性与模型治理 | 6–10 天 | Trace、成本、单一真源、Prompt 版本 | 否 |
| Phase 5 | 鉴权、存储与生产部署 | 7–12 天 | RBAC、MinIO、全容器、健康检查 | 公开部署阻断 |
| Phase 6 | 性能、局部重算与发布收尾 | 4–7 天 | 并发优化、Bundle 优化、发布证据 | 否 |

单人建议总工期约 7–10 周。若需先交付最小可用版本，优先完成 Phase 0、1、2，并至少完成 Phase 3 的安全隔离最小版本。

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
- README 已按实现演进更新：pgvector 已进入 Agent 主链并保留 citation/degraded 状态；
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

#### F. Tool Calling 指标

- tool selection accuracy：需要工具时是否选择正确工具；
- no-tool accuracy：不需要工具时是否避免多余调用；
- argument schema pass rate：参数一次通过 JSON Schema 的比例；
- tool task completion rate：执行并回填结果后是否完成最终任务；
- permission denial correctness：跨 owner、越权工具调用是否稳定拒绝；
- injection resistance：材料/检索内容能否诱导模型调用未授权工具；
- 平均调用轮数、工具延迟、失败恢复率和单任务工具预算消耗。

EduFlowBench 新增不少于 15 个版本化工具案例，覆盖正确选型、无需调用、参数修复、
空结果、超时、可重试失败、权限拒绝、Prompt Injection 和调用轮数耗尽。确定性规则
负责 Schema/权限/调用轨迹判定，LLM Judge 只评价最终任务质量。

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

## 6. Phase 2：统一编排、真正 RAG 与真实 Tool Calling

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
Planner / Knowledge Tool Loop
  ├── knowledge_search
  ├── material_lookup
  └── get_project_context
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

### 6.5 真实 Tool Calling Runtime

首版只开放与教学任务直接相关的只读工具：

- `knowledge_search`：检索知识库并返回带 source ID 的证据；
- `material_lookup`：读取当前 owner/project 明确授权且已解析的素材；
- `get_project_context`：读取当前项目的主题、参数、锁帧和版本摘要。

运行闭环必须是：

```text
LLM 决策 → Tool Registry 查找 → JSON Schema 校验 → Policy/owner 校验
        → 超时与预算控制 → 真实服务执行 → 结构化 ToolResult 回填
        → LLM 继续推理或结束
```

工程要求：

- 使用统一 `ToolSpec`/Registry，声明名称、版本、参数 Schema、读写级别和超时；
- 工具执行上下文由服务端注入 user/project/request/workflow/node ID，模型不得伪造；
- 限制最大调用轮数、单轮并发、总耗时、结果字符数和 Token/成本；
- 参数非法时允许一次受控修复，禁止无限自纠错循环；
- 明确区分 retryable、permission_denied、invalid_arguments、not_found 和 timeout；
- 每次调用记录 `tool_call_id`、工具版本、参数摘要、状态、耗时和结果摘要到 Node Trace；
- 工具返回内容视为不可信数据，回填时使用清晰的数据边界；
- 首版禁止 Shell、任意文件访问、任意 SQL、Docker Socket 和写操作；
- 写工具未来必须单独审批、幂等键、审计和补偿机制，不复用只读策略。

验收标准：

- 至少 3 个真实只读工具进入 Planner/Knowledge 主链；
- 模型可以自主选择 0–N 个工具，并基于真实返回结果形成最终输出；
- 非法参数、越权资源、注入诱导和超轮次均被确定性拒绝；
- 所有工具调用可由 workflow/node trace 定位，且不记录原始敏感材料；
- EduFlowBench 工具集不少于 15 例，关键安全用例通过率必须为 100%。

### 6.6 真正的局部重算

已完成的底座：手动 scope 会确定性选择目标帧，只把目标旧帧与活动参数送入 Coder；
合并时保留范围外帧、锁定帧、稳定 Frame ID 及非帧元数据。`local` 参数仅持久化并由
前端表现层应用，不触发 LLM；任一结构性参数则显式进入 `all_frames` 重算。

已完成参数到 Frame 的显式/推断依赖、后继状态传播、执行前影响预览、并发指纹校验和
版本语义差异 UI。参数影响会复用生成器 `requires` DAG 传递至 video 等下游产物，预览展示
跨产物范围并写入过期标记；相应模块成功重生成后清除标记。仍需以真实 Trace 验证局部重算的
成本与时延收益，并按成本策略决定是否自动调度下游重生成。

### 6.7 Phase 2 完成定义

- 所有生成入口共用一张 LangGraph；
- 中断后可在进程重启后继续；
- pgvector 检索进入实际生成链并产生引用；
- 具备检索降级路径；
- 独立模块并发执行且有上限；
- 至少 3 个真实工具完成模型自主选择、执行结果回填、权限控制与 Trace 闭环；
- Tool Calling Eval 覆盖选择、参数、完成率和安全拒绝；
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

采用“不可变 Artifact Version + 查询投影”方案；当前已完成聚合版本底座：

- `project_versions.dsl_snapshot` 保存不可变完整产物；
- `projects.current_version_id` 指向当前版本；
- `frames` 表作为当前版本的查询/编辑投影；
- `module_outputs` 不再复制完整 Frames，只保存 artifact reference；
- 编辑帧时基于 `base_version` 创建新版本；
- 使用 `revision` 乐观锁防止覆盖；
- 导出任务固定绑定 `source_artifact_version`；
- 恢复历史版本不原地修改旧版本；
- 增加一致性校验和修复脚本。

其中不可变 `project_versions`、原子 `current_version_id`、Frames 查询投影、dirty working-copy
语义、恢复不修改历史版本以及导出固定版本已经落地。`module_outputs.frames` 的完整数组已改为
指向所属 ProjectVersion 的 artifact reference，Alembic 0020 负责迁移存量 JSONB，活动读取会
从 Frames 真源水合兼容投影，并提供默认只读的一致性审计/窄范围引用修复脚本。逐帧编辑目前标记
working copy 为 dirty，由显式保存或工作流完成
建立新版本，避免为每次键入自动创建高频版本。

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

## 10. Phase 6：性能优化与发布收尾

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
- [x] 模块重试前以成功 Trace 的单模块费用中位数展示预计成本；无计价样本时明确不可估算，并展示工作流硬上限；
- 参数局部重算差异预览；
- 质量报告展示确定性错误与 Judge 建议的区别；
- 引用可展开查看原始知识片段；
- [x] 导出明确绑定不可变 ProjectVersion，Worker 不再读取执行时的可变项目状态；
- 管理页展示任务、成本和 Eval 趋势。

### 10.4 发布证据

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

- [x] `.env`、API Key、数据库密码未进入 Git 和镜像层；Compose 秘密无隐式默认值。
- [x] Prompt 不写入 Trace；Endpoint、工具参数/结果摘要和公开失败信息经过敏感信息脱敏。
- [x] 用户材料具有保留期限和删除能力。
- [x] 业务资源查询统一校验 owner/role；管理员跨 owner 策略显式化，项目、素材、后台任务与
  导出状态/下载的跨租户和 404 隐藏语义由授权矩阵回归测试覆盖。
- [x] 上传、解析、Prompt/Tool、生成代码、下载已形成独立威胁模型并链接对应测试证据。
- [x] Manim 执行沙箱无网络、无宿主凭证、无 Docker Socket。
- [x] API 有生产写入/生成速率限制，LLM/模块/Tool 有并发上限，工作流有 Token 和成本硬预算。
- [x] Prompt Injection 测试覆盖用户主题、材料、检索文档与 ToolResult；进入 XML-like
  Prompt 前统一编码标记字符，真实模型攻击率仍待在线 Bench。
- [x] 审计事件为只追加模型，未向普通用户暴露修改或删除 API；查询入口强制 admin、采用
  有界 cursor 分页和脱敏摘要。
- [x] 通用 HTTP、SSE、模块和导出错误响应不包含 Traceback、路径、Prompt 或凭证。

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

### Epic H：性能和发布

- H1 Backend concurrency tuning
- H2 Local recompute
- H3 Frontend code splitting
- H4 Architecture/ADR
- H5 Benchmark report/demo
- H6 Release metrics

### Epic I：Tool Calling Runtime

- I1 ToolSpec、Registry 与版本协议
- I2 Tool Execution Context 与 owner/policy 校验
- I3 多轮模型调用与 ToolResult 回填循环
- I4 超时、轮数、并发、结果大小和成本预算
- I5 Tool Call Node Trace 与审计摘要
- I6 Tool Calling EduFlowBench 与注入/越权测试

---

## 15. 里程碑验收表

| 里程碑 | 必须满足的结果 |
|---|---|
| M0 可信仓库 | 前后端 CI 全绿；依赖锁定；README 与事实一致 |
| M1 可评估 Agent | EduFlowBench ≥50 例；确定性+Judge；有基线报告 |
| M2 真正 Agent Workflow | 单一 Graph；检索入链；引用可追踪；至少 3 个真实工具形成受控调用闭环 |
| M3 可恢复且安全 | 队列持久化；重启恢复；生成代码隔离；安全测试通过 |
| M4 可运营 | Trace、成本、指标、告警、Prompt/模型版本化 |
| M5 可公开部署 | Auth/RBAC、MinIO、完整 Compose、Readiness |
| M6 发布就绪 | 指标稳定、文档完整、演示视频、可复现部署 |

---

## 16. 最小交付版本与完整版本

### 16.1 最小交付版本

时间有限时必须完成：

1. Phase 0 全部；
2. EduFlowBench 30–50 个案例；
3. 确定性正确性评测与一次模型对比；
4. pgvector 接入主链并带引用；
5. 统一正常生成与 HITL 恢复路径；
6. 至少 3 个只读工具完成模型自主选择、权限校验、结果回填和 Trace；
7. Manim 至少迁移到无网络、无凭证的独立 Worker；
8. 一份包含 Tool Calling 指标的真实 Benchmark 报告。

此时可作为具备基础评测、检索、工作流和安全隔离能力的最小工程版本交付。

### 16.2 完整工程版本

在最小版本上继续完成：

- 持久化任务与 Worker 恢复；
- 全链路 Trace 和成本治理；
- 数据单一真源；
- 鉴权与多租户；
- MinIO 和完整容器化；
- 局部重算与性能优化。
- 写工具审批/幂等/补偿（首版只读 Tool Calling 不包含写工具）。

此时可作为覆盖生产治理、平台能力和 Agent 基础设施的完整工程版本交付。

---

## 17. 明确暂不优先的事项

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

## 18. 执行纪律

每个改造 PR 必须回答：

1. 它解决了哪个缺陷编号？
2. 是否改变 Workflow、Prompt、模型、DSL 或数据 Schema？
3. 使用什么测试和 Eval 证明没有回归？
4. 对延迟、Token、成本和安全有什么影响？
5. 是否需要迁移、回滚或 Feature Flag？
6. 文档和架构图是否同步？

任何涉及 Prompt、模型、检索或工作流的变更，没有 EduFlowBench 对比结果不得直接发布；任何涉及生成代码执行的变更，没有沙箱安全测试不得公开部署。
