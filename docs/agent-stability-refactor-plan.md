# EduFlow Agent 稳定生成链改造计划

> 适用版本：v1.0（以 `algorithm-trace-v1` 为协议基线）

## 0. 改造结论

当前反复失败的主要矛盾不是“校验器不够宽松”，而是模型同时承担了两类不适合交给模型的工作：

1. 生成教学表达（适合 LLM）；
2. 计算算法事实和最终状态（应由程序确定性推导）。

因此改造方向是 **收窄模型职责、固定协议、程序推导状态、分层判定**，而不是继续给校验器增加随机兼容分支。兼容层可以吸收历史字段和表达差异，但不能把错误距离、错误前驱、错误访问顺序改成“正确答案”。

## 0.1 优先级和完成定义

| 优先级 | 目标 | 完成定义 |
| --- | --- | --- |
| P0 | 让结果可复现、可追溯 | 每份报告记录 SHA、数据集、Prompt、Schema、模型、参数；失败能回放，不依赖重新调用模型 |
| P1 | 让模型输出稳定可解析 | 结构化协议、输入归一化、定向重试和原始/归一化审计证据完整 |
| P2 | 让算法语义不再依赖模型 | Dijkstra/Bellman-Ford/BFS/DFS 的状态由事件和程序状态机推导 |
| P3 | 形成可用于简历的评测证据 | 3 例 Smoke 通过后再跑 10/50 例，并能复核质量、延迟、成本和失败分类 |

## 0.2 明确不采用的方案

- 不通过删除失败样本、提高超时、无限增加重试来制造通过率。
- 不把所有校验降级为 warning；Schema、引用完整性和算法语义仍是硬门禁。
- 不在没有最新提交 SHA 和审计产物的情况下宣称“50/50”“Judge 平均分”或 p95。
- 不因为模型偶尔输出非法 JSON，就把核心状态改成字符串再由正则猜测。

## 1. 目标与边界

目标不是通过放宽算法校验提高通过率，而是建立一条可复现、可审计的生成链：

```
固定评测基线 → 结构化协议 → 输入归一化 → 程序推导状态 → 分层校验 → 分阶段评测
```

归一化只允许修复表达形式，不允许修改算法事实。距离、访问顺序、前驱边、路径树等语义必须由程序推导或校验；语义冲突继续阻断生成。

## 2. 当前状态

| 项目 | 状态 | 证据 |
| --- | --- | --- |
| 版本化 Algorithm Trace 协议 | 已完成 | `agent/schema/algorithm_trace.py` |
| 旧字段与等价结构归一化 | 已完成 | `agent/tools/normalize_dsl.py` |
| Dijkstra / Bellman-Ford / BFS / DFS 确定性模拟 | 已完成 | `agent/tools/algorithm_simulator.py` |
| 事件到规范状态的编译 | 已完成 | `agent/tools/algorithm_trace_compiler.py` |
| Prompt 与 Structured Output 约束 | 已完成 | `agent/agents/prompts.py`、`llm_client.py` |
| 分层硬门禁 | 已完成 | `agent/evals/graders/deterministic.py` |
| 原始输出、归一化结果、最终判定审计证据 | 已完成 | `agent/evals/runners/run_online.py` |
| 后端测试 | 已完成 | `1143 passed, 6 skipped` |
| 线上 3 例 Smoke | 待执行 | 离线回放 3/3 通过，需在 `dev-v1.0` 最新 SHA 上运行 |
| 线上 10/50 例正式评测 | 待 Smoke 通过后执行 | 不提前消耗模型预算 |

相关提交：

- `cdd652a feat: compile algorithm traces deterministically`
- `e6fea3c feat: persist benchmark audit evidence`
- `81ae637 fix: stabilize algorithm trace normalization and replay`

## 2.1 待改造问题与根因映射

| 现象 | 根因 | 正确处理 |
| --- | --- | --- |
| JSON 截断/字段别名导致解析失败 | 长输出和自由字段过多 | 缩短协议、分阶段生成、Schema 约束、只重试当前帧 |
| Dijkstra/Bellman-Ford 状态不一致 | 让模型直接填写距离、队列、visited | 模型只给操作事件，程序推导状态 |
| `chart`/`quiz` 等对象导致渲染失败 | DSL 类型集合与模型认知不一致 | 协议枚举化；未知类型明确丢弃并留审计告警，主结构仍可渲染 |
| 每次失败都重跑整轮 | 失败分类和回放边界不清 | 按 `format/semantic/provider/render/judge` 分类，优先离线回放 |
| 线上运行耗时过长 | 50 例直接串行调用、输出过长、无早停 | 3→10→50 分阶段，Smoke 失败立即停止，限制单 case 输出和预算 |
| CI 失败但报告已生成 | “生成结果”和“门禁结果”耦合 | 先保存报告和 artifact，再单独执行 enforce；报告可用于诊断，门禁决定 job 状态 |

## 3. 分阶段执行顺序

### 阶段 A：固定评测基线（P0）

每次报告固定记录：

- `git_sha`
- `dataset_version` 与数据集 SHA256
- `prompt_version`
- 候选模型与 Judge 模型
- `temperature=0`（若服务支持，同时固定 `seed`）
- `response_format`
- `schema_version`

首轮只运行：

```
alg_dijkstra_basic
alg_dijkstra_unreachable
alg_bellman_ford_negative
```

Smoke 必须满足：

```
passed_cases = 3
algorithm_invariant_pass = 1.0
dsl_schema_pass = 1.0
reference_integrity_pass = 1.0
```

### 阶段 B：统一协议与归一化（P1）

规范状态统一采用 `algorithm-trace-v1`：

```json
{
  "schema_version": "algorithm-trace-v1",
  "algorithm": "dijkstra",
  "phase": "relax",
  "dist": {"s": 0, "A": 3},
  "visited": ["s"],
  "queue": [{"vertex": "A", "priority": 3}],
  "predecessor": {"A": "s"}
}
```

归一化层可兼容 `vertices/nodes`、`from/to`、二维队列项、`A(3)` 字符串、快照内显式图边和旧队列字段；Bellman-Ford 的边扫描统一进入 `edge_scan`，不伪装成优先队列。所有转换必须记录 `normalization_applied`、`repair_count`、`repair_types`。错误距离、错误前驱、不存在的图边和非法访问顺序禁止自动修复；无事件帧中的 visited/queue 仅作为可审计展示提示，最终状态由确定性模拟器生成。

### 阶段 C：从源头收敛模型输出（P1）

Prompt 明确禁止别名和自由状态字段，并提供正确/错误示例。优先使用 JSON Schema；不支持 Schema 的模型降级到 JSON Object，再由本地 Pydantic 严格校验。失败时只对当前帧定向重生成，携带原始帧、前后状态、失败规则、允许修改字段和禁止修改字段。

### 阶段 D：程序推导算法状态（P2）

模型只生成教学意图和操作事件，例如：

```json
{"operation": "relax", "source": "B", "target": "D", "weight": 5}
```

程序负责推导 `dist`、`visited`、`queue`、`predecessor` 和路径树。首批覆盖 Dijkstra、Bellman-Ford、BFS、DFS；其他教学内容继续走通用 DSL，按算法逐步迁移。

### 阶段 E：分层校验与失败处理（P2）

硬门禁阻断 JSON/DSL Schema、Frame ID 唯一性、图结构稳定性、距离/访问顺序/前驱边/路径树不一致、引用缺失和 Algorithm Trace 编译问题。软告警不直接阻断，例如讲解文本截断、交互问题偏少和非主流程帧缺少展示细节。

失败统一分类为 `format_error`、`semantic_error`、`provider_error`、`render_error` 或 `judge_error`，避免无差别重跑模型。

### 阶段 F：离线变体回放（P2）

参数化测试覆盖队列二维数组、对象数组、字符串、旧图字段、Bellman-Ford 对比帧、负环、不可达节点、空上下文和材料冲突。优先回放历史 artifact；只有 Prompt、Schema、模型、状态机、归一化规则或数据集变化时才重新调用线上模型。

### 阶段 G：线上分阶段评测（P3）

固定顺序：

1. 3 例 Smoke，确认分支 SHA 和元数据；
2. 10 例小批量，检查成本、延迟、重试和归一化修复率；
3. 50 例正式评测，保存完整审计产物。

每轮保存：

```
quality-online-report.json
quality-online-artifacts/*.json
quality-online-artifacts/*.audit.json
git_sha / dataset_sha / prompt_version
candidate_model / judge_model / response_format
```

每个 case 的 audit 文件必须同时包含 `raw_coder_output`、`normalization_report`、`normalized_artifact` 和 `final_decision`。

## 3.1 推荐实施批次

### 批次 1：基线与回放（半天）

1. 固定当前提交、数据集 SHA、Prompt/Schema 版本和模型参数。
2. 用历史 artifact 做离线回放，确认报告生成、审计文件和门禁互相独立。
3. 先不调用线上模型；任何失败都先定位为代码、协议或数据问题。

验收：`pytest agent/tests -q` 通过；历史 3 例离线回放可复现；报告包含完整元数据。

### 批次 2：协议和归一化（1 天）

1. 统一 `algorithm-trace-v1`，旧字段只在归一化入口兼容。
2. 明确 `graph`、`events`、`dist`、`predecessor`、`edge_scan` 的职责。
3. 记录每次修复的 `repair_types`，禁止静默修改语义字段。

验收：覆盖二维队列、字符串队列、旧图字段、Bellman 边扫描等历史变体；语义冲突仍能被硬门禁拦截。

### 批次 3：程序推导状态（1～2 天）

1. 模型只生成 `relax/visit/scan/enqueue` 等操作事件。
2. 状态机生成距离、前驱、访问顺序、队列和路径树。
3. 保留模型原始输出用于解释，但最终 DSL 使用编译后的规范状态。

验收：同一组事件多次编译得到字节级一致的规范状态；Dijkstra、Bellman-Ford、BFS、DFS 各有回归样例。

### 批次 4：失败处理和渲染降级（1 天）

1. 将失败分为格式、语义、Provider、渲染、Judge 五类。
2. 格式失败只重试当前帧，语义失败进入反思或人工修订，Provider 失败按退避重试。
3. 无法渲染的非核心视觉对象转为审计 warning；核心帧、引用和算法状态仍阻断。

验收：每类失败都有明确错误码、重试上限和可读诊断；不会因为一个非核心对象让整轮无审计结果。

### 批次 5：线上 Smoke 和正式评测（按成本推进）

1. 3 例 Smoke：只验证协议、确定性门禁和服务可用性。
2. 10 例：观察成本、p50/p95、截断率、归一化修复率和失败分类。
3. 50 例：固定模型、参数和数据集后运行一次正式评测，保留全部 artifact。

验收：Smoke 3/3 后才允许扩大样本；50 例必须能从 SHA 和 artifact 复核。

## 4. 评测指标与简历使用规则

统计产物成功率、确定性规则通过率、Judge 平均分、p50/p95 端到端延迟、模型重试率、截断率、归一化修复率和单 case/整轮成本。

指标口径固定如下：

- **产物成功率**：生成、归一化、硬门禁和渲染均完成的 case / 总 case；
- **确定性规则通过率**：不包含 Judge 主观分的硬门禁通过 case / 总 case；
- **端到端延迟**：从 runner 发起 case 到最终判定写入报告，按 case 统计，再计算 p50/p95；
- **重试率/截断率**：分别统计 provider 重试和 `finish_reason=length` 的 case 数，不把重试后的成功隐藏掉；
- **归一化修复率**：发生表达层修复的 case / 总 case，必须同时报告语义修复数（应为 0）。

简历只写能由提交 SHA 和 artifact 复核的数字。例如“50 例中 7 例发生格式归一化，0 例发生语义修复”。在 50 例完成前，不写“50/50”、Judge 平均分或 p95；可先写本地测试数量和已完成的架构能力。

## 5. 验收、回滚与完成定义

每阶段执行：

```powershell
python -m pytest agent/tests -q
git diff --check
git status --short
```

线上失败先下载并回放已有 artifact，再判断是否确需重调模型。若只是校验器、报告或 CI 门禁变化，优先本地回放；只有 Prompt、Schema、模型、状态机、归一化规则或数据集变化才重跑 Smoke。

最终必须同时满足：

1. 格式偏差可被记录的归一化层吸收；
2. 算法语义错误仍被硬门禁阻断；
3. Dijkstra、Bellman-Ford、BFS、DFS 状态可由程序复现；
4. 3 例 Smoke 在最新提交上通过；
5. 50 例 Benchmark 可重复运行；
6. 报告可追溯原始输出、归一化结果和最终判定；
7. 简历数字与线上审计产物一一对应。

## 6. 每次改动后的执行清单

```powershell
# 1. 本地静态和单元验证
python -m pytest agent/tests -q
git diff --check

# 2. 离线回放（优先于重新调用模型）
Set-Location agent
python -m evals.runners.run_offline \
  --dataset evals/datasets/eduflowbench_v1.jsonl \
  --artifacts-dir <artifact-dir> \
  --output <replay-report.json>

# 3. 只在协议/Prompt/模型/状态机/数据集变化后运行线上 Smoke
# GitHub Actions: Online EduFlowBench Quality
# case_limit=3，确认报告中 git_sha 为当前提交

# 4. Smoke 通过后再将 case_limit 调整为 10，最后为 50
```

每轮失败处理顺序固定为：

1. 下载 `quality-online-report.json` 和全部 audit artifact；
2. 读取 `failure_category`、原始输出和归一化报告；
3. 若能离线复现，先修代码/协议并回放；
4. 只有外部模型、Prompt、Schema 或数据集变化时才重调线上模型；
5. 新结果通过后再更新简历数字。
