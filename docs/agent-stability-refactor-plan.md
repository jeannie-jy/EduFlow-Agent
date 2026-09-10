# EduFlow Agent 稳定生成链改造计划

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

## 4. 评测指标与简历使用规则

统计产物成功率、确定性规则通过率、Judge 平均分、p50/p95 端到端延迟、模型重试率、截断率、归一化修复率和单 case/整轮成本。

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
