"""Compare two EduFlowBench JSON reports and enforce regression thresholds."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_GATES = {
    "pass_rate": {"direction": "higher", "max_regression": 0.02, "severity": "error"},
    "dsl_schema_pass": {"direction": "higher", "max_regression": 0.0, "severity": "error"},
    "forbidden_claim_pass": {"direction": "higher", "max_regression": 0.0, "severity": "error"},
    "oracle_pass": {"direction": "higher", "max_regression": 0.02, "severity": "error"},
    "p95_latency_ms": {"direction": "lower", "max_regression": 0.20, "severity": "warning"},
    "mean_cost_usd": {"direction": "lower", "max_regression": 0.20, "severity": "warning"},
}


def _metric(report: dict[str, Any], name: str) -> float | None:
    summary = report.get("summary", {})
    value = summary.get(name, summary.get("metric_means", {}).get(name))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def compare_reports(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    gates: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return machine-readable deltas; missing metrics are explicitly skipped."""

    comparisons = []
    for name, gate in (gates or DEFAULT_GATES).items():
        old = _metric(baseline, name)
        new = _metric(candidate, name)
        if old is None or new is None:
            comparisons.append({"metric": name, "status": "skipped", "reason": "metric_missing"})
            continue

        if gate["direction"] == "higher":
            regression = old - new
        elif old == 0:
            regression = 0.0 if new <= 0 else float("inf")
        else:
            regression = (new - old) / abs(old)

        threshold = float(gate["max_regression"])
        regressed = regression > threshold
        comparisons.append({
            "metric": name,
            "baseline": old,
            "candidate": new,
            "regression": regression,
            "threshold": threshold,
            "severity": gate["severity"],
            "status": "failed" if regressed else "passed",
        })

    failures = [c for c in comparisons if c.get("status") == "failed" and c["severity"] == "error"]
    warnings = [c for c in comparisons if c.get("status") == "failed" and c["severity"] == "warning"]
    return {
        "schema_version": "1.0",
        "baseline_run": baseline.get("run", {}),
        "candidate_run": candidate.get("run", {}),
        "passed": not failures,
        "failure_count": len(failures),
        "warning_count": len(warnings),
        "comparisons": comparisons,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    comparison = compare_reports(baseline, candidate)
    rendered = json.dumps(comparison, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if comparison["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
