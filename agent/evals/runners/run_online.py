"""Opt-in online EduFlowBench runner with bounded concurrency and cost metadata."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
import json
import math
import os
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
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
    repetitions: int = 1,
) -> dict[str, Any]:
    """Generate and grade cases. The injected generator owns provider credentials."""

    if budget_usd is not None and budget_usd <= 0:
        raise ValueError("budget_usd must be greater than zero")
    if repetitions <= 0:
        raise ValueError("repetitions must be greater than zero")
    # A shared monetary budget cannot be enforced safely while multiple unknown-cost
    # cases start concurrently. Budgeted release runs therefore serialize case starts.
    semaphore = asyncio.Semaphore(1 if budget_usd is not None else max(1, concurrency))
    spent_cost_usd = 0.0
    budget_exhausted = False

    async def execute(case: EvalCase, repeat_index: int) -> dict[str, Any]:
        nonlocal budget_exhausted, spent_cost_usd
        queued_at = time.perf_counter()
        execution_started: float | None = None
        try:
            async with semaphore:
                execution_started = time.perf_counter()
                if budget_usd is not None and spent_cost_usd >= budget_usd:
                    budget_exhausted = True
                    finished = time.perf_counter()
                    return {
                        "case_id": case.case_id,
                        "repeat_index": repeat_index,
                        "passed": False,
                        "metrics": {},
                        "issues": ["generation skipped: run cost budget exhausted"],
                        "latency_ms": round((finished - execution_started) * 1000, 2),
                        "processing_latency_ms": round(
                            (finished - execution_started) * 1000, 2
                        ),
                        "latency_recorded": False,
                        "queue_wait_ms": round(
                            (execution_started - queued_at) * 1000, 2
                        ),
                        "wall_clock_latency_ms": round(
                            (finished - queued_at) * 1000, 2
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
                result["repeat_index"] = repeat_index
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
                            if isinstance(judged.get("latency_ms"), (int, float)):
                                result["judge_latency_ms"] = judged["latency_ms"]
                            if isinstance(judged.get("cost_usd"), (int, float)):
                                judge_cost = max(float(judged["cost_usd"]), 0.0)
                                total_case_cost += judge_cost
                                spent_cost_usd += judge_cost
                        except Exception as exc:
                            result["passed"] = False
                            result.setdefault("issues", []).append(
                                f"judge failed: {type(exc).__name__}: {exc}"
                            )
                            result["judge_error"] = type(exc).__name__
                # Keep the auditable decision separate from the generator
                # metadata so raw provider output, canonical artifact and the
                # final gate outcome can be inspected independently.
                result["final_decision"] = {
                    "passed": bool(result.get("passed")),
                    "metrics": result.get("metrics", {}),
                    "issues": result.get("issues", []),
                }
                # Backward-compatible aggregate fields used by report summaries.
                result["usage"] = generated.get("usage", {})
                result["cost_usd"] = round(total_case_cost, 8)
                metadata = generated.get("metadata")
                if isinstance(metadata, dict):
                    result["generator_metadata"] = metadata
                if artifacts_dir:
                    artifacts_dir.mkdir(parents=True, exist_ok=True)
                    artifact_stem = (
                        case.case_id
                        if repetitions == 1
                        else f"{case.case_id}.repeat-{repeat_index:02d}"
                    )
                    (artifacts_dir / f"{artifact_stem}.json").write_text(
                        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    metadata = result.get("generator_metadata", {})
                    audit_payload = {
                        "case_id": case.case_id,
                        "raw_coder_output": metadata.get("raw_coder_output", {}),
                        "normalization_report": metadata.get("normalization_report", {}),
                        "normalized_artifact": artifact,
                        "final_decision": result.get("final_decision", {}),
                    }
                    if repetitions > 1:
                        audit_payload["repeat_index"] = repeat_index
                    (artifacts_dir / f"{artifact_stem}.audit.json").write_text(
                        json.dumps(
                            audit_payload,
                            ensure_ascii=False,
                            indent=2,
                        )
                        + "\n",
                        encoding="utf-8",
                    )
                finished = time.perf_counter()
                processing_latency_ms = round(
                    (finished - execution_started) * 1000, 2
                )
                result["latency_ms"] = processing_latency_ms
                result["processing_latency_ms"] = processing_latency_ms
                result["latency_recorded"] = True
                result["queue_wait_ms"] = round(
                    (execution_started - queued_at) * 1000, 2
                )
                result["wall_clock_latency_ms"] = round(
                    (finished - queued_at) * 1000, 2
                )
                return result
        except Exception as exc:
            finished = time.perf_counter()
            processing_latency_ms = round(
                (finished - execution_started) * 1000, 2
            ) if execution_started is not None else 0.0
            return {
                "case_id": case.case_id,
                "repeat_index": repeat_index,
                "passed": False,
                "metrics": {},
                "issues": [f"generation failed: {type(exc).__name__}: {exc}"],
                "latency_ms": processing_latency_ms,
                "processing_latency_ms": processing_latency_ms,
                "latency_recorded": execution_started is not None,
                "queue_wait_ms": round(
                    ((execution_started or finished) - queued_at) * 1000, 2
                ),
                "wall_clock_latency_ms": round(
                    (finished - queued_at) * 1000, 2
                ),
            }

    results = await asyncio.gather(
        *(
            execute(case, repeat_index)
            for case in cases
            for repeat_index in range(1, repetitions + 1)
        )
    )
    summary = _aggregate(results, len(cases))
    outcomes_by_case: defaultdict[str, list[bool]] = defaultdict(list)
    for result in results:
        outcomes_by_case[str(result.get("case_id"))].append(bool(result.get("passed")))
    flaky_case_ids = sorted(
        case_id
        for case_id, outcomes in outcomes_by_case.items()
        if len(set(outcomes)) > 1
    )
    stable_pass_case_count = sum(
        bool(outcomes) and all(outcomes)
        for outcomes in outcomes_by_case.values()
    )
    summary.update({
        "repetition_count": repetitions,
        "attempt_count": len(results),
        "evaluated_case_count": len(outcomes_by_case),
        "missing_case_count": max(0, len(cases) - len(outcomes_by_case)),
        "stable_pass_case_count": stable_pass_case_count,
        "stable_pass_rate": round(stable_pass_case_count / len(cases), 4) if cases else 0.0,
        "flaky_case_count": len(flaky_case_ids),
        "flaky_case_ids": flaky_case_ids,
        "flaky_rate": round(len(flaky_case_ids) / len(cases), 4) if cases else 0.0,
    })
    summary["missing_artifacts"] = summary["missing_case_count"]
    # `latency_ms` is retained as a compatibility alias, but percentile metrics
    # deliberately use processing time after semaphore acquisition.  In budgeted
    # runs the semaphore serializes cases, so timing before acquisition would
    # incorrectly include queue wait and make later cases look progressively slower.
    latencies = sorted(
        float(item["processing_latency_ms"])
        for item in results
        if item.get("latency_recorded", True)
        and isinstance(item.get("processing_latency_ms"), (int, float))
    )
    queue_waits = [
        float(item["queue_wait_ms"])
        for item in results
        if isinstance(item.get("queue_wait_ms"), (int, float))
    ]
    wall_clock_latencies = sorted(
        float(item["wall_clock_latency_ms"])
        for item in results
        if isinstance(item.get("wall_clock_latency_ms"), (int, float))
    )
    costs = [
        float(item["cost_usd"])
        for item in results
        if isinstance(item.get("cost_usd"), (int, float))
    ]
    if latencies:
        p50_index = max(0, math.ceil(len(latencies) * 0.50) - 1)
        p95_index = max(0, math.ceil(len(latencies) * 0.95) - 1)
        summary["latency_basis"] = "processing_latency_ms"
        summary["latency_sample_count"] = len(latencies)
        summary["mean_latency_ms"] = round(sum(latencies) / len(latencies), 2)
        summary["p50_latency_ms"] = latencies[p50_index]
        summary["p95_latency_ms"] = latencies[p95_index]
    if queue_waits:
        summary["mean_queue_wait_ms"] = round(sum(queue_waits) / len(queue_waits), 2)
    if wall_clock_latencies:
        wall_clock_p95_index = max(
            0, math.ceil(len(wall_clock_latencies) * 0.95) - 1
        )
        summary["wall_clock_p95_latency_ms"] = wall_clock_latencies[
            wall_clock_p95_index
        ]
    if costs:
        summary["mean_cost_usd"] = round(sum(costs) / len(costs), 6)
        summary["total_cost_usd"] = round(sum(costs), 6)
    if budget_usd is not None:
        summary["budget_usd"] = budget_usd
        summary["budget_exceeded"] = (
            budget_exhausted or summary.get("total_cost_usd", 0) > budget_usd
        )
    normalization_reports = [
        item.get("generator_metadata", {}).get("quality_report", {}).get("normalization")
        for item in results
        if isinstance(item.get("generator_metadata"), dict)
    ]
    normalization_reports = [
        report for report in normalization_reports if isinstance(report, dict)
    ]
    if normalization_reports:
        repaired_cases = sum(bool(report.get("applied")) for report in normalization_reports)
        repair_count = sum(
            int(report.get("repair_count", 0))
            for report in normalization_reports
            if isinstance(report.get("repair_count", 0), (int, float))
        )
        summary["normalization_case_count"] = len(normalization_reports)
        summary["normalization_repaired_cases"] = repaired_cases
        summary["normalization_repair_count"] = repair_count
        summary["normalization_repair_rate"] = round(
            repaired_cases / len(normalization_reports), 4
        )
    compilation_reports = [
        item.get("generator_metadata", {}).get("algorithm_trace_compilation")
        for item in results
        if isinstance(item.get("generator_metadata"), dict)
    ]
    compilation_reports = [
        report for report in compilation_reports if isinstance(report, dict) and report
    ]
    if compilation_reports:
        compiled_frames = sum(
            int(report.get("frames_compiled", 0))
            for report in compilation_reports
            if isinstance(report.get("frames_compiled", 0), (int, float))
        )
        event_frames = sum(
            int(report.get("event_frames", 0))
            for report in compilation_reports
            if isinstance(report.get("event_frames", 0), (int, float))
        )
        compilation_issues = sum(
            len(report.get("issues", []))
            for report in compilation_reports
            if isinstance(report.get("issues"), list)
        )
        summary["algorithm_trace_compilation_case_count"] = len(compilation_reports)
        summary["algorithm_trace_compiled_frames"] = compiled_frames
        summary["algorithm_trace_event_frames"] = event_frames
        summary["algorithm_trace_compilation_issue_count"] = compilation_issues
    sorting_reports = [
        item.get("generator_metadata", {}).get("sorting_trace_compilation")
        for item in results
        if isinstance(item.get("generator_metadata"), dict)
    ]
    sorting_reports = [
        report for report in sorting_reports if isinstance(report, dict) and report
    ]
    if sorting_reports:
        summary["sorting_trace_compilation_case_count"] = len(sorting_reports)
        summary["sorting_trace_compiled_frames"] = sum(
            int(report.get("frames_compiled", 0))
            for report in sorting_reports
            if isinstance(report.get("frames_compiled", 0), (int, float))
        )
        summary["sorting_trace_compilation_issue_count"] = sum(
            len(report.get("issues", []))
            for report in sorting_reports
            if isinstance(report.get("issues"), list)
        )
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
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


def _report_exit_code(report: dict[str, Any], *, fail_on_flaky: bool = False) -> int:
    passed = report["summary"]["passed_cases"] == len(report["results"])
    within_budget = not report["summary"].get("budget_exceeded", False)
    flaky_ok = not fail_on_flaky or report["summary"].get("flaky_rate", 0.0) == 0
    return 0 if passed and within_budget and flaky_ok else 1


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    parser.add_argument(
        "--limit",
        type=int,
        help="evaluate only the first N dataset cases (useful for low-cost smoke runs)",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="skip this many dataset cases before applying --limit",
    )
    parser.add_argument("--judge-generator", help="Async judge as module:function")
    parser.add_argument("--judge-model")
    parser.add_argument(
        "--repetitions",
        type=int,
        default=1,
        help="repeat every selected case N times for stability/flaky-rate measurement",
    )
    parser.add_argument(
        "--fail-on-flaky",
        action="store_true",
        help="return a failing exit code when any repeated case has mixed outcomes",
    )
    args = parser.parse_args()

    if os.getenv("EDUFLOW_ALLOW_ONLINE_EVAL") != "1":
        parser.error("set EDUFLOW_ALLOW_ONLINE_EVAL=1 to acknowledge external calls and cost")
    if bool(args.judge_generator) != bool(args.judge_model):
        parser.error("--judge-generator and --judge-model must be provided together")
    if args.judge_model and args.judge_model == args.model:
        parser.error("judge model must differ from candidate model")
    if args.repetitions <= 0:
        parser.error("--repetitions must be greater than zero")

    all_cases = load_cases(args.dataset)
    if args.offset < 0:
        parser.error("--offset must be non-negative")
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be greater than zero")
    cases = all_cases[args.offset:]
    if args.limit is not None:
        cases = cases[:args.limit]
    if not cases:
        parser.error("case selection is empty")

    report = asyncio.run(run_online_cases(
        cases,
        _load_generator(args.generator),
        concurrency=args.concurrency,
        timeout_seconds=args.timeout_seconds,
        artifacts_dir=args.artifacts_dir,
        run_metadata={
            "model": args.model,
            "candidate_model": args.model,
            "prompt_version": args.prompt_version,
            "budget_usd": args.budget_usd,
            "dataset": str(args.dataset),
            "dataset_version": args.dataset.stem,
            "dataset_sha256": _sha256_file(args.dataset),
            "dataset_total_cases": len(all_cases),
            "case_offset": args.offset,
            "case_limit": args.limit,
            "generator": args.generator,
            "judge_generator": args.judge_generator,
            "judge_model": args.judge_model,
            "response_format": "auto(json_schema->json_object)",
            "temperature": 0.0,
            "temperature_policy": "eval_deterministic",
            "algorithm_trace_schema": "algorithm-trace-v1",
            "normalization_enabled": True,
            "repetitions": args.repetitions,
        },
        budget_usd=args.budget_usd,
        judge=_load_generator(args.judge_generator) if args.judge_generator else None,
        repetitions=args.repetitions,
    ))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return _report_exit_code(report, fail_on_flaky=args.fail_on_flaky)


if __name__ == "__main__":
    raise SystemExit(main())
