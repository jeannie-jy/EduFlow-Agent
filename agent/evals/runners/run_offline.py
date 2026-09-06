"""Run deterministic EduFlowBench graders against saved JSON artifacts."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evals.graders import grade_artifact, grade_tool_calls
from evals.models import EvalCase, load_cases


def _aggregate(results: list[dict[str, Any]], total_cases: int) -> dict[str, Any]:
    evaluated = len(results)
    passed = sum(bool(result["passed"]) for result in results)
    metric_keys = sorted({key for result in results for key in result["metrics"]})
    metric_means: dict[str, float] = {}
    for key in metric_keys:
        numeric = [
            float(result["metrics"][key])
            for result in results
            if isinstance(result["metrics"].get(key), (bool, int, float))
            and result["metrics"].get(key) is not None
        ]
        if numeric:
            metric_means[key] = round(sum(numeric) / len(numeric), 4)
    injection_results = [result for result in results if "prompt-injection" in result.get("tags", [])]
    summary = {
        "dataset_cases": total_cases,
        "evaluated_cases": evaluated,
        "missing_artifacts": total_cases - evaluated,
        "passed_cases": passed,
        "pass_rate": round(passed / evaluated, 4) if evaluated else 0.0,
        "metric_means": metric_means,
    }
    if injection_results:
        summary["prompt_injection_resistance_rate"] = round(
            sum(bool(result["metrics"].get("forbidden_claim_pass")) for result in injection_results)
            / len(injection_results),
            4,
        )
    return summary


def _git_sha() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return os.getenv("GITHUB_SHA") or os.getenv("EDUFLOW_GIT_SHA")


async def run_dataset(
    cases: list[EvalCase],
    artifacts_dir: Path,
    *,
    run_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for case in cases:
        artifact_path = artifacts_dir / f"{case.case_id}.json"
        if not artifact_path.exists():
            continue
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        result = (
            grade_tool_calls(case, artifact)
            if case.tools is not None
            else await grade_artifact(case, artifact)
        )
        result["artifact_path"] = str(artifact_path)
        results.append(result)
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run": {
            "git_sha": _git_sha(),
            "workflow_version": os.getenv("EDUFLOW_WORKFLOW_VERSION", "legacy-v1"),
            "prompt_version": os.getenv("EDUFLOW_PROMPT_VERSION", "unversioned"),
            "model": os.getenv("EDUFLOW_EVAL_MODEL"),
            "temperature": None,
            "budget_usd": None,
            **(run_metadata or {}),
        },
        "summary": _aggregate(results, len(cases)),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--artifacts-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-all", action="store_true")
    parser.add_argument("--run-id")
    parser.add_argument("--model")
    parser.add_argument("--prompt-version")
    parser.add_argument("--workflow-version")
    args = parser.parse_args()

    cases = load_cases(args.dataset)
    metadata = {
        key: value
        for key, value in {
            "run_id": args.run_id,
            "model": args.model,
            "prompt_version": args.prompt_version,
            "workflow_version": args.workflow_version,
        }.items()
        if value is not None
    }
    report = asyncio.run(run_dataset(cases, args.artifacts_dir, run_metadata=metadata))
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)

    summary = report["summary"]
    if args.require_all and summary["missing_artifacts"]:
        return 2
    return 0 if summary["passed_cases"] == summary["evaluated_cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
