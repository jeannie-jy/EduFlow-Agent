"""Opt-in end-to-end RAG groundedness benchmark for the production graph."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import get_settings
from evals.graders.retrieval import grade_retrieval
from evals.models import EvalCase, load_cases
from evals.runners.run_online import run_online_cases
from evals.runners.run_offline import _git_sha
from evals.generators.live_workflow import generate_workflow_case


def _source_ids_from_artifact(artifact: dict[str, Any]) -> list[str]:
    graph = artifact.get("knowledge_graph") or {}
    sources = graph.get("sources", []) if isinstance(graph, dict) else []
    return [
        str(source.get("source_id"))
        for source in sources
        if isinstance(source, dict) and source.get("source_id")
    ]


def _grade_groundedness(case: EvalCase, result: dict[str, Any]) -> dict[str, Any]:
    """Grade evidence propagation after the normal deterministic DSL checks."""
    metadata = result.get("generator_metadata") or {}
    retrieval = metadata.get("retrieval") or {}
    artifact = result.get("artifact") or {}
    retrieved_ids = [
        str(source.get("source_id"))
        for source in retrieval.get("sources", [])
        if isinstance(source, dict) and source.get("source_id")
    ]
    cited_ids = [
        str(item)
        for item in (
            metadata.get("artifact_source_ids")
            or metadata.get("knowledge_source_ids")
            or _source_ids_from_artifact(artifact)
        )
    ]
    retrieval_metrics = grade_retrieval(case, retrieved_ids, cited_ids)
    is_abstention = bool(
        case.retrieval and case.retrieval.must_abstain_without_evidence
    )
    if is_abstention:
        abstention_pass = (
            retrieval.get("status") == "no_evidence"
            and not retrieved_ids
            and not cited_ids
        )
        groundedness_pass = bool(result.get("passed")) and abstention_pass
        retrieval_metrics["abstention_pass"] = abstention_pass
        retrieval_metrics["evidence_propagation_pass"] = abstention_pass
    else:
        relevant = set(case.retrieval.relevant_document_ids) if case.retrieval else set()
        evidence_hit = bool(relevant & set(retrieved_ids))
        source_propagation_pass = bool(relevant & set(cited_ids))
        groundedness_pass = (
            bool(result.get("passed"))
            and evidence_hit
            and source_propagation_pass
            and retrieval_metrics["citation_coverage"] == 1.0
            and retrieval_metrics["citation_correctness"] == 1.0
        )
        retrieval_metrics["abstention_pass"] = None
        retrieval_metrics["evidence_propagation_pass"] = source_propagation_pass

    retrieval_metrics["retrieved_document_ids"] = retrieved_ids
    retrieval_metrics["cited_document_ids"] = cited_ids
    retrieval_metrics["retrieval_status"] = retrieval.get("status", "missing")
    return {
        "passed": groundedness_pass,
        "metrics": retrieval_metrics,
        "issues": []
        if groundedness_pass
        else ["RAG evidence was not retrieved and propagated into the DSL"],
    }


async def evaluate(
    cases: list[EvalCase],
    *,
    output: Path,
    artifacts_dir: Path | None,
    concurrency: int,
    timeout_seconds: float,
    budget_usd: float | None,
    model: str,
) -> dict[str, Any]:
    report = await run_online_cases(
        cases,
        generate_workflow_case,
        concurrency=concurrency,
        timeout_seconds=timeout_seconds,
        artifacts_dir=artifacts_dir,
        budget_usd=budget_usd,
        run_metadata={
            "mode": "online_rag_groundedness",
            "dataset": "retrieval_production_v1",
            "model": model,
            "generator": "evals.generators.live_workflow:generate_workflow_case",
        },
    )
    passed = 0
    rag_metrics: list[dict[str, Any]] = []
    for case, result in zip(cases, report["results"], strict=True):
        graded = _grade_groundedness(case, result)
        result["rag_groundedness_passed"] = graded["passed"]
        result["rag_metrics"] = graded["metrics"]
        if not graded["passed"]:
            result.setdefault("issues", []).extend(graded["issues"])
        passed += int(graded["passed"])
        rag_metrics.append(graded["metrics"])

    summary = report["summary"]
    summary["groundedness_evaluable_cases"] = len(cases)
    summary["groundedness_passed_cases"] = passed
    summary["groundedness_pass_rate"] = round(passed / len(cases), 4) if cases else 0.0
    for name in ("recall_at_k", "precision_at_k", "mrr", "citation_coverage", "citation_correctness"):
        values = [float(item[name]) for item in rag_metrics if isinstance(item.get(name), (int, float))]
        if values:
            summary[f"rag_{name}_mean"] = round(sum(values) / len(values), 4)
    abstentions = [item["abstention_pass"] for item in rag_metrics if item.get("abstention_pass") is not None]
    if abstentions:
        summary["rag_abstention_pass_rate"] = round(
            sum(bool(value) for value in abstentions) / len(abstentions), 4
        )
    report["run"].update({
        "git_sha": _git_sha(),
        "embedding_model": get_settings().embedding_model,
        "embedding_dimension": get_settings().embedding_dimension,
        "concurrency": concurrency,
    })
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--artifacts-dir", type=Path)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--timeout-seconds", type=float, default=300)
    parser.add_argument("--budget-usd", type=float)
    parser.add_argument("--model", default=os.getenv("LLM_MODEL", "configured-model"))
    args = parser.parse_args()
    if os.getenv("EDUFLOW_ALLOW_ONLINE_EVAL") != "1":
        parser.error("set EDUFLOW_ALLOW_ONLINE_EVAL=1 to acknowledge external calls and cost")
    if args.concurrency <= 0:
        parser.error("--concurrency must be greater than zero")
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be greater than zero")
    if args.offset < 0:
        parser.error("--offset must be non-negative")
    cases = load_cases(args.dataset)
    cases = cases[args.offset :]
    if args.limit is not None:
        cases = cases[: args.limit]
    if not cases:
        parser.error("case selection is empty")
    report = asyncio.run(evaluate(
        cases,
        output=args.output,
        artifacts_dir=args.artifacts_dir,
        concurrency=args.concurrency,
        timeout_seconds=args.timeout_seconds,
        budget_usd=args.budget_usd,
        model=args.model,
    ))
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0 if report["summary"]["groundedness_passed_cases"] == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
