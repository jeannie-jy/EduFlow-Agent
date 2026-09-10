"""Opt-in retrieval-only benchmark against the production knowledge corpus."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evals.graders.retrieval import grade_retrieval
from evals.models import EvalCase, load_cases
from evals.runners.run_offline import _git_sha
from config import get_settings
from services.retrieval import retrieve_knowledge_context


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    return values[max(0, math.ceil(len(values) * fraction) - 1)]


async def evaluate_case(case: EvalCase) -> dict[str, Any]:
    started = time.perf_counter()
    context = await retrieve_knowledge_context(case.topic)
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    retrieved_ids = [str(source["source_id"]) for source in context.get("sources", [])]
    metrics = grade_retrieval(case, retrieved_ids)
    if case.retrieval and case.retrieval.must_abstain_without_evidence:
        metrics["abstention_pass"] = not retrieved_ids
        passed = bool(metrics["abstention_pass"])
        retrieval_evaluable = False
    else:
        metrics["abstention_pass"] = None
        passed = metrics["recall_at_k"] > 0
        retrieval_evaluable = True
    return {
        "case_id": case.case_id,
        "passed": passed,
        "retrieval_evaluable": retrieval_evaluable,
        "metrics": metrics,
        "retrieved_document_ids": retrieved_ids,
        "status": context.get("status"),
        "candidate_count": context.get("candidate_count", 0),
        "selected_count": context.get("selected_count", 0),
        "context_chars": context.get("context_chars", 0),
        "latency_ms": latency_ms,
        "issues": [] if passed else ["retrieval expectation not satisfied"],
    }


async def evaluate(cases: list[EvalCase], *, concurrency: int = 1) -> dict[str, Any]:
    if concurrency <= 0:
        raise ValueError("concurrency must be greater than zero")
    semaphore = asyncio.Semaphore(concurrency)

    async def bounded(case: EvalCase) -> dict[str, Any]:
        async with semaphore:
            return await evaluate_case(case)

    results = await asyncio.gather(*(bounded(case) for case in cases))
    latencies = sorted(float(result["latency_ms"]) for result in results)
    metric_names = (
        "recall_at_k",
        "precision_at_k",
        "mrr",
        "abstention_pass",
    )
    metric_means: dict[str, float] = {}
    for name in metric_names:
        values = [
            float(result["metrics"][name])
            for result in results
            if result["retrieval_evaluable"] or name == "abstention_pass"
            if isinstance(result["metrics"].get(name), (int, float))
        ]
        if values:
            metric_means[name] = round(sum(values) / len(values), 4)
    summary: dict[str, Any] = {
        "dataset_cases": len(cases),
        "evaluated_cases": len(results),
        "retrieval_evaluable_cases": sum(
            bool(result["retrieval_evaluable"]) for result in results
        ),
        "abstention_cases": sum(
            not bool(result["retrieval_evaluable"]) for result in results
        ),
        "passed_cases": sum(bool(result["passed"]) for result in results),
        "pass_rate": round(
            sum(bool(result["passed"]) for result in results) / len(results), 4
        )
        if results
        else 0.0,
        "metric_means": metric_means,
        "latency_basis": "retrieval_processing_ms",
        "latency_sample_count": len(latencies),
        "mean_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else None,
        "p50_latency_ms": _percentile(latencies, 0.50),
        "p95_latency_ms": _percentile(latencies, 0.95),
    }
    settings = get_settings()
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run": {
            "git_sha": _git_sha(),
            "mode": "online_retrieval",
            "dataset": "retrieval_production_v1",
            "embedding_model": settings.embedding_model,
            "embedding_dimension": settings.embedding_dimension,
            "similarity_threshold": settings.knowledge_similarity_threshold,
            "concurrency": concurrency,
        },
        "summary": summary,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="maximum concurrent embedding requests (default: 1)",
    )
    args = parser.parse_args()
    if os.getenv("EDUFLOW_ALLOW_ONLINE_EVAL") != "1":
        parser.error("set EDUFLOW_ALLOW_ONLINE_EVAL=1 to acknowledge embedding calls and cost")
    cases = load_cases(args.dataset)
    if args.limit is not None:
        if args.limit <= 0:
            parser.error("--limit must be greater than zero")
        cases = cases[: args.limit]
    if args.concurrency <= 0:
        parser.error("--concurrency must be greater than zero")
    report = asyncio.run(evaluate(cases, concurrency=args.concurrency))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0 if report["summary"]["passed_cases"] == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
