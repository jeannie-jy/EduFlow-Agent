# EduFlowBench 在线评测操作手册

本手册用于在代码、数据集和评测配置固定后运行线上质量评测。不要跳过 3 例 Smoke 直接运行 50 例。

## 1. 运行前检查

在本地确认最新提交已经推送到目标分支：

```powershell
git status -sb
git log -1 --oneline
git push origin dev-v1.0
```

GitHub Actions 页面中选择 `Online EduFlowBench Quality`，确认 Branch 使用刚刚推送的分支。

Repository Secrets（密钥）只放以下内容：

```text
EDUFLOW_EVAL_LLM_API_KEY
EDUFLOW_EVAL_EMBEDDING_API_KEY
EDUFLOW_EVAL_JUDGE_API_KEY
```

Repository Variables（非敏感价格）放以下内容：

```text
EDUFLOW_LLM_INPUT_COST_PER_MILLION
EDUFLOW_LLM_OUTPUT_COST_PER_MILLION
EDUFLOW_JUDGE_INPUT_COST_PER_MILLION
EDUFLOW_JUDGE_OUTPUT_COST_PER_MILLION
```

价格单位是美元/百万 Token，必须按实际供应商价目填写。未知价格时可以暂时填 `0`，但报告中的成本只能解释为未估算，而不能作为真实成本结论。

## 2. 先运行 3 例 Smoke

Actions 表单建议填写：

| 输入 | Smoke 值 |
| --- | --- |
| Candidate endpoint | 候选模型的 OpenAI-compatible `/v1` 地址 |
| Candidate model | 当前候选模型，例如 `deepseek-v4-flash` |
| Embedding endpoint/model/dimension | 与数据库向量维度一致，例如 `text-embedding-v4 / 1024` |
| Judge endpoint | 独立 Judge 的 OpenAI-compatible `/v1` 地址 |
| Judge model | 必须不同于候选模型，例如 `qwen3.8-flash` |
| Maximum reported total run cost | `5.00` |
| Number of cases to run (`case_limit`) | `3` (`case_limit=3`) |

Smoke 只覆盖：

```text
alg_dijkstra_basic
alg_dijkstra_unreachable
alg_bellman_ford_negative
```

只有以下条件全部满足，才允许扩大样本：

```text
passed_cases = 3
algorithm_invariant_pass = 1.0
dsl_schema_pass = 1.0
reference_integrity_pass = 1.0
```

同时打开生成的 `quality-online-report.json`，核对：

```text
run.git_sha == 当前分支最新提交
run.dataset_sha256 与本次数据集一致
run.prompt_version == workflow-v2
run.candidate_model 与表单一致
run.judge_model 与表单一致
```

## 3. 10 例小批量

Smoke 通过后，只把 `Number of cases to run` 改为 `10`，其他参数保持不变。重点观察：

- `passed_cases` 和 `pass_rate`；
- `p50_latency_ms`、`p95_latency_ms`；
- `normalization_repair_rate`；
- `finish_reason=length` 和重试次数；
- `total_cost_usd`；
- 各类 `failure_category`。

如果只是校验器或报告逻辑变化，优先使用已有 artifact 离线回放，不要重新付费调用模型。

## 4. 50 例正式评测

10 例稳定后，将样本数改为 `50`，固定候选模型、Judge、Prompt、数据集和价格变量。保存 Actions artifact 中的：

```text
quality-online-report.json
quality-online-artifacts/
compose-ps.txt
agent-api.log
```

正式结果只有在报告和提交 SHA 可复核时才可以写入简历。

## 5. 失败后的处理顺序

1. 先下载报告、audit 文件和日志；
2. 区分 `format_error`、`semantic_error`、`provider_error`、`render_error`、`judge_error`；
3. 如果已有 artifact，先在本地离线回放：

```powershell
Set-Location agent
python -m evals.runners.run_offline `
  --dataset evals/datasets/eduflowbench_v1.jsonl `
  --artifacts-dir <artifact-dir> `
  --output <replay-report.json>
```

4. 只有 Prompt、Schema、模型、状态机、归一化规则或数据集变化时，才重新运行线上 Smoke；
5. 不要通过删除失败样本、关闭硬门禁或无限重试来提高通过率。

## 6. 简历证据规则

可以写入简历的数字必须能从报告和 artifact 复核，例如：

```text
50 例产物生成成功率
确定性规则通过率
独立 Judge 平均分
p95 端到端延迟
单例/整轮成本
格式归一化修复率与语义修复数
```

在 50 例正式评测完成前，不要提前写 `50/50`、Judge 平均分或 p95。
