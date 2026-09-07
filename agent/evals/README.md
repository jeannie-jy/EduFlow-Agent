# EduFlowBench

EduFlowBench is the versioned, domain-specific evaluation suite for EduFlow-Agent. It measures the generated teaching artifact instead of using unrelated general-agent leaderboards.

## Dataset contract

The v1 dataset is JSONL. Each case contains the input topic, constraints, expected concepts, forbidden claims, frame bounds, and an optional executable oracle. Dataset loading is strict and rejects malformed or duplicate case IDs.

## Offline evaluation

Place one RenderScript JSON artifact per case under an artifact directory:

```text
artifacts/
├── alg_dijkstra_basic.json
└── alg_bubble_sort_basic.json
```

Then run:

```bash
cd agent
python -m evals.runners.run_offline \
  --dataset evals/datasets/eduflowbench_v1.jsonl \
  --artifacts-dir artifacts \
  --output evals/reports/offline.json
```

Add `--require-all` in release evaluation to fail when any expected artifact is missing. Offline graders never call a model and cover schema validity, frame-state consistency, visual-object references, required/forbidden concepts, frame bounds, and executable final-state oracles.

Compare a candidate with a stable report using:

```bash
python -m evals.runners.compare_runs \
  evals/reports/baseline.json evals/reports/candidate.json
```

Quality regressions return a non-zero exit code. Latency and cost increases over
20% are reported as warnings. Reports carry the git revision plus workflow,
prompt, and model metadata so comparisons remain auditable.

The online runner accepts an async `module:function` generator, records latency,
token usage and cost, and enforces bounded concurrency. It refuses to start
unless `EDUFLOW_ALLOW_ONLINE_EVAL=1` is set, preventing ordinary CI from spending
model credits accidentally. Judge requests are versioned and blinded; a semantic
score cannot override a deterministic failure. Human calibration reports exact
agreement, within-one agreement, MAE, and Cohen's kappa.

For a low-cost smoke run, select a subset before launching any paid evaluation:

```bash
python -m evals.runners.run_online \
  --dataset evals/datasets/eduflowbench_v1.jsonl \
  --limit 3 \
  --offset 0 \
  ...
```

The manual GitHub Actions workflows expose the same `case_limit` input. Use
`3-5` to verify credentials, schema validity, and end-to-end latency; use the
full dataset value (`50` for quality or `8` for Tool Calling) only for a release
run. A smoke report must never be mixed with a full-dataset report.

When `--budget-usd` is supplied, the runner serializes case starts and stops
launching new cases once reported spend reaches the run budget. This makes the
flag an execution-time gate rather than a post-run label; the provider may still
bill the final in-flight request that crosses the threshold.

### Production LangGraph quality benchmark

`evals.generators.live_workflow:generate_workflow_case` runs each of the 50 core
cases through the same Planner–Knowledge–Coder–Quality–Reflection graph used by
the application. It returns the generated RenderScript plus per-workflow input/
output Tokens, estimated cost, and the internal quality report. Each case uses a
fresh checkpoint thread so reruns cannot inherit prior graph state.

```bash
EDUFLOW_ALLOW_ONLINE_EVAL=1 \
EDUFLOW_EVAL_JUDGE_ENDPOINT=https://api.example.com/v1 \
EDUFLOW_EVAL_JUDGE_API_KEY=... \
EDUFLOW_EVAL_JUDGE_MODEL=independent-model \
python -m evals.runners.run_online \
  --dataset evals/datasets/eduflowbench_v1.jsonl \
  --generator evals.generators.live_workflow:generate_workflow_case \
  --output evals/reports/quality-online.json \
  --artifacts-dir evals/reports/quality-online-artifacts \
  --concurrency 1 \
  --timeout-seconds 300 \
  --model "$LLM_MODEL" \
  --prompt-version workflow-v2 \
  --judge-generator evals.generators.live_judge:judge_workflow_case \
  --judge-model "$EDUFLOW_EVAL_JUDGE_MODEL" \
  --budget-usd 10
```

The manual `Online EduFlowBench Quality` workflow starts isolated dependencies,
runs this command, uploads the report/artifacts/logs, and always tears the stack
down. `live_judge` uses separately configured endpoint/key/model values, validates
all seven rubric dimensions, treats the candidate artifact as bounded untrusted
data, and cannot override deterministic failures. It records candidate and Judge
Token/cost separately. A report is not publishable until this independent Judge
run and the required human calibration have actually completed.

Prepare a deterministic blinded review sheet for at least 20% of the completed
core run. Candidate/Judge identities and Judge scores are omitted from this file:

```bash
python -m evals.runners.human_review prepare \
  --dataset evals/datasets/eduflowbench_v1.jsonl \
  --report evals/reports/quality-online.json \
  --artifacts-dir evals/reports/quality-online-artifacts \
  --sample-rate 0.2 \
  --output evals/reports/human-review.json
```

After a reviewer fills every 1–5 rubric score and `overall_score`, validate the
coverage and calculate overall plus per-criterion exact agreement,
within-one agreement, MAE, and Cohen's kappa:

```bash
python -m evals.runners.human_review score \
  --review evals/reports/human-review.json \
  --report evals/reports/quality-online.json \
  --min-rate 0.2 \
  --output evals/reports/human-calibration.json
```

Preparation fails if any dataset case, independent Judge result, or artifact is
missing. Scoring fails on duplicate cases, incomplete/out-of-range labels, rubric
mismatch, or insufficient coverage.

### Real Tool Calling benchmark

`evals.generators.live_tools:generate_tool_case` connects the online runner to
the same bounded multi-round Tool Runtime used by the Knowledge node. It invokes
the configured real model and executes the production `knowledge_search`,
`material_lookup`, and `get_project_context` handlers. Run it only against an
isolated evaluation database:

```bash
EDUFLOW_ALLOW_ONLINE_EVAL=1 \
EDUFLOW_EVAL_BOOTSTRAP=1 \
python -m evals.runners.run_online \
  --dataset evals/datasets/tool_online_cases.jsonl \
  --generator evals.generators.live_tools:generate_tool_case \
  --output evals/reports/tool-online.json \
  --model "$LLM_MODEL" \
  --prompt-version tool-router-v1 \
  --budget-usd 2
```

`EDUFLOW_EVAL_BOOTSTRAP=1` writes stable fixture rows and must never be enabled
against production. For a pre-seeded environment, omit it and set
`EDUFLOW_EVAL_PROJECT_ID` plus `EDUFLOW_EVAL_MATERIAL_ID`. The manual
`Online Tool Calling Bench` workflow creates an ephemeral Compose database,
requires repository evaluation secrets, uploads the report and per-case traces,
and fails when the cases or reported cost budget fail. It is never scheduled or
called by default CI. Set the repository variables
`EDUFLOW_LLM_INPUT_COST_PER_MILLION` and
`EDUFLOW_LLM_OUTPUT_COST_PER_MILLION` for the selected model; otherwise the
report keeps Token counts but its LLM cost estimate is zero. Embedding-provider
cost is not included in that LLM estimate.

## Evaluation policy

- Deterministic failures are blocking and cannot be overwritten by an LLM judge.
- Online model generation and LLM judging use an explicit opt-in runner or a separate scheduled workflow.
- Every report records model, prompt, workflow, and source versions.
- Generated reports are build artifacts and are not committed unless selected as a release baseline.
