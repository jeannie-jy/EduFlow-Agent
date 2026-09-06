"""Opt-in online EduFlowBench runner with bounded concurrency and cost metadata."""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import os
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evals.graders import (
    JudgeResult,
    grade_artifact,
    grade_tool_calls,
    merge_judge_with_deterministic,
)
from evals.models import EvalCase, load_cases
from evals.runners.run_offline import _aggregate, _git_sha

Generator = Callable[[EvalCase], Awaitable[dict[str, Any]]]
Judge = Callable[
    [EvalCase, dict[str, Any], dict[str, Any]],
    Awaitable[dict[str, Any]],
]


async def run_online_cases(
    cases: list[EvalCase],
    generator: Generator,
    *,
    concurrency: int = 2,
    timeout_seconds: float = 180.0,
    artifacts_dir: Path | None = None,
    run_metadata: dict[str, Any] | None = None,
    budget_usd: float | None = None,
    judge: Judge | None = None,
) -> dict[str, Any]:
    """Generate and grade cases. The injected generator owns provider credentials."""

    if budget_usd is not None and budget_usd <= 0:
        raise ValueError("budget_usd must be greater than zero")
    # A shared monetary budget cannot be enforced safely while multiple unknown-cost
    # cases start concurrently. Budgeted release runs therefore serialize case starts.
    semaphore = asyncio.Semaphore(1 if budget_usd is not None else max(1, concurrency))
    spent_cost_usd = 0.0
    budget_exhausted = False

    async def execute(case: EvalCase) -> dict[str, Any]:
        nonlocal budget_exhausted, spent_cost_usd
        started = time.perf_counter()
        try:
            async with semaphore:
                if budget_usd is not None and spent_cost_usd >= budget_usd:
                    budget_exhausted = True
                    return {
                        "case_id": case.case_id,
                        "passed": False,
                        "metrics": {},
                        "issues": ["generation skipped: run cost budget exhausted"],
                        "latency_ms": round(
                            (time.perf_counter() - started) * 1000, 2
                        ),
                        "usage": {},
                        "cost_usd": 0.0,
                    }
                generated = await asyncio.wait_for(
                    generator(case), timeout=timeout_seconds
                )
                artifact = generated.get("artifact", generated)
                result = (
                    grade_tool_calls(case, artifact)
                    if case.tools is not None
                    else await grade_artifact(case, artifact)
                )
                candidate_cost = generated.get("cost_usd")
                total_case_cost = (
                    max(float(candidate_cost), 0.0)
                    if isinstance(candidate_cost, (int, float))
                    else 0.0
                )
                # Candidate spend has already occurred and must be charged even if
                # deterministic grading or the independent Judge later fails.
                spent_cost_usd += total_case_cost
                result["candidate_usage"] = generated.get("usage", {})
                result["candidate_cost_usd"] = candidate_cost

                if judge is not None and case.tools is None:
                    if (
                        budget_usd is not None
                        and spent_cost_usd >= budget_usd
                    ):
                        budget_exhausted = True
                        result["passed"] = False
                        result.setdefault("issues", []).append(
                            "judge skipped: run cost budget exhausted"
                        )
                    else:
                        try:
                            judged = await asyncio.wait_for(
                                judge(case, artifact, result), timeout=timeout_seconds
                            )
                            judge_result = JudgeResult.model_validate(
                                judged.get("judge", judged)
                            ).validated_criteria()
                            result = merge_judge_with_deterministic(
                                result, judge_result
                            )
                            result["judge_usage"] = judged.get("usage", {})
                            result["judge_cost_usd"] = judged.get("cost_usd")
                            if isinstance(judged.get("cost_usd"), (int, float)):
                                judge_cost = max(float(judged["cost_usd"]), 0.0)
                                total_case_cost += judge_cost
                                spent_cost_usd += judge_cost
                        except Exception as exc:  # noqa: BLE001 - preserve candidate accounting
                            result["passed"] = False
                            result.setdefault("issues", []).append(
                                f"judge failed: {type(exc).__name__}: {exc}"
                            )
                            result["judge_error"] = type(exc).__name__
                result["latency_ms"] = round(
                    (time.perf_counter() - started) * 1000, 2
                )
                # Backward-compatible aggregate fields used by report summaries.
                result["usage"] = generated.get("usage", {})
                result["cost_usd"] = round(total_case_cost, 8)
                metadata = generated.get("metadata")
                if isinstance(metadata, dict):
                    result["generator_metadata"] = metadata
                if artifacts_dir:
                    artifacts_dir.mkdir(parents=True, exist_ok=True)
                    (artifacts_dir / f"{case.case_id}.json").write_text(
                        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
                return result
        except Exception as exc:  # noqa: BLE001 - isolate each external case failure
            return {
                "case_id": case.case_id,
                "passed": False,
                "metrics": {},
                "issues": [f"generation failed: {type(exc).__name__}: {exc}"],
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            }

    results = await asyncio.gather(*(execute(case) for case in cases))
    summary = _aggregate(results, len(cases))
    latencies = sorted(float(item["latency_ms"]) for item in results)
    costs = [
        float(item["cost_usd"])
        for item in results
        if isinstance(item.get("cost_usd"), (int, float))
    ]
    if latencies:
        summary["p95_latency_ms"] = latencies[max(0, int(len(latencies) * 0.95) - 1)]
    if costs:
        summary["mean_cost_usd"] = round(sum(costs) / len(costs), 6)
        summary["total_cost_usd"] = round(sum(costs), 6)
    if budget_usd is not None:
        summary["budget_usd"] = budget_usd
        summary["budget_exceeded"] = (
            budget_exhausted or summary.get("total_cost_usd", 0) > budget_usd
        )
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run": {"git_sha": _git_sha(), "mode": "online", **(run_metadata or {})},
        "summary": summary,
        "results": results,
    }


def _load_generator(spec: str) -> Generator:
    module_name, separator, attribute = spec.partition(":")
    if not separator:
        raise ValueError("generator must use module:function syntax")
    generator = getattr(importlib.import_module(module_name), attribute)
    if not callable(generator):
        raise TypeError(f"generator is not callable: {spec}")
    return generator


def _report_exit_code(report: dict[str, Any]) -> int:
    passed = report["summary"]["passed_cases"] == len(report["results"])
    within_budget = not report["summary"].get("budget_exceeded", False)
    return 0 if passed and within_budget else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--generator", required=True, help="Async callable as module:function")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--artifacts-dir", type=Path)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=float, default=180)
    parser.add_argument("--model", required=True)
    parser.add_argument("--prompt-version", required=True)
    parser.add_argument("--budget-usd", type=float)
    parser.add_argument("--judge-generator", help="Async judge as module:function")
    parser.add_argument("--judge-model")
    args = parser.parse_args()

    if os.getenv("EDUFLOW_ALLOW_ONLINE_EVAL") != "1":
        parser.error("set EDUFLOW_ALLOW_ONLINE_EVAL=1 to acknowledge external calls and cost")
    if bool(args.judge_generator) != bool(args.judge_model):
        parser.error("--judge-generator and --judge-model must be provided together")
    if args.judge_model and args.judge_model == args.model:
        parser.error("judge model must differ from candidate model")

    report = asyncio.run(run_online_cases(
        load_cases(args.dataset),
        _load_generator(args.generator),
        concurrency=args.concurrency,
        timeout_seconds=args.timeout_seconds,
        artifacts_dir=args.artifacts_dir,
        run_metadata={
            "model": args.model,
            "prompt_version": args.prompt_version,
            "budget_usd": args.budget_usd,
            "dataset": str(args.dataset),
            "generator": args.generator,
            "judge_generator": args.judge_generator,
            "judge_model": args.judge_model,
        },
        budget_usd=args.budget_usd,
        judge=_load_generator(args.judge_generator) if args.judge_generator else None,
    ))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return _report_exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
