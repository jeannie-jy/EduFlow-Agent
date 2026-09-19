# EduFlowBench v1 release baseline — 2026-09-19

Status: **PASS**

This baseline records the first selected 50-case production-workflow run after
the deterministic finalization and independent-Judge availability fixes. The
raw smoke and formal reports are committed beside this document.

## Provenance

| Field | Value |
| --- | --- |
| Git commit | `4fa775d3cdd53e7acfdd24c830265f25a353a0ed` |
| Actions artifact | `online-quality-bench-35374703389` |
| Dataset | `eduflowbench_v1` (50 cases) |
| Dataset SHA-256 | `ed49c0333f47bf51e71c0eff9b4d1d685fbdbe96820dbcecda7c60f18e13b7bf` |
| Candidate model | `deepseek-v4-flash` |
| Independent Judge | `qwen3.8-flash` |
| Prompt version | `workflow-v2` |
| Candidate temperature | `0.0` |
| Algorithm trace schema | `algorithm-trace-v1` |
| Run budget | USD 10.00 |
| Smoke generated | `2026-09-19T01:47:05.281695+08:00` |
| Formal report generated | `2026-09-19T03:06:14.171066+08:00` |

## Gate results

| Measurement | Smoke | Formal |
| --- | ---: | ---: |
| Selected cases | 3 | 50 |
| Repetitions | 3 | 1 |
| Attempts | 9 | 50 |
| Passed | 9/9 | 50/50 |
| Pass rate | 100% | 100% |
| Stable pass rate | 100% | 100% |
| Flaky cases | 0 | 0 |
| Missing artifacts reported by runner | 0 | 0 |
| Judge completed | 9/9 | 50/50 |
| Judge errors | 0 | 0 |
| Judge coverage | 100% | 100% |
| Prompt-injection resistance | not part of smoke subset | 100% |
| Reported cost | USD 0.066429 | USD 0.369794 |
| Budget exceeded | no | no |

Every reported formal deterministic metric passed at 100%, including DSL
schema validity, unique frame IDs, state consistency, algorithm invariants,
reference integrity, required-concept coverage, forbidden-claim checks, frame
bounds, executable oracles, and algorithm-trace compilation.

## Independent-Judge observations

The Judge is advisory: it cannot override deterministic blocking failures and
this run did not configure a semantic-score threshold. Therefore `50/50` is a
statement about the repository's deterministic release gates, not a claim that
every semantic rubric score was perfect.

| Criterion | Mean (1–5) | Minimum |
| --- | ---: | ---: |
| Overall | 3.7664 | 2.0 |
| Factual correctness | 3.44 | 1.0 |
| Clarity | 3.88 | 2.0 |
| Teaching sequence | 3.74 | 2.0 |
| Topic alignment | 4.86 | 3.0 |
| Interaction quality | 2.56 | 1.0 |
| Completeness | 4.30 | 3.0 |
| Audience fit | 4.00 | 2.0 |

Interaction quality and low-scoring factual cases remain improvement targets.
A publishable semantic-quality claim should add blinded human calibration for
at least 20% of cases as described in the evaluation runbook.

## Cost and latency

Formal-run usage and estimated cost:

- Candidate: 1,097,919 input Tokens, 369,407 output Tokens, USD 0.257143.
- Judge: 311,714 input Tokens, 183,525 output Tokens, USD 0.112651.
- Processing latency: mean 94,942.67 ms, p50 83,691.70 ms, p95 151,174.23 ms.
- Wall-clock p95 including the serialized budget queue: 4,522,204.91 ms.

Provider billing remains authoritative; these costs use the rates configured
for this workflow run.

## Deterministic repair observations

- 18 cases exposed normalization reports; all 18 applied normalization, with
  116 recorded normalization repairs in total.
- Finalization used targeted frame fallback in 3/50 cases (6%):
  `alg_bubble_sort_basic`, `alg_merge_sort`, and `os_thread_mutex`.
- Each fallback replaced one invalid frame with a safe text frame; all three
  final artifacts passed the deterministic gates.
- Algorithm and sorting trace compilation reported zero issues.

The three targeted fallbacks are accepted by this baseline but remain quality
debt to reduce in later runs.

## Committed evidence

| File | SHA-256 |
| --- | --- |
| [`quality-smoke-report.json`](quality-smoke-report.json) | `46f24cb01069a372d29ec18220479263c7c64dba55b3bd2f5f7b57e8cf137ed7` |
| [`quality-online-report.json`](quality-online-report.json) | `c35ef0b03d269913f1acf3911fa9b7ecc3488842f6014720de79a51e10f387b5` |

The supplied download contained the two reports, not the separate
`quality-online-artifacts/`, `compose-ps.txt`, or `agent-api.log` entries from
the Actions artifact. Retrieve those from `online-quality-bench-35374703389`
while retained if full per-case artifact replay or infrastructure-log audit is
needed.

The reports contain the prompt-injection test phrase `API Key` as test data;
no credential value is stored in this baseline.
