"""Deterministic information-retrieval and citation metrics."""

from __future__ import annotations

from typing import Any

from evals.models import EvalCase


def grade_retrieval(
    case: EvalCase,
    retrieved_document_ids: list[str],
    cited_document_ids: list[str] | None = None,
) -> dict[str, Any]:
    if case.retrieval is None:
        raise ValueError(f"case has no retrieval expectation: {case.case_id}")
    relevant = set(case.retrieval.relevant_document_ids)
    ranked = retrieved_document_ids[:case.retrieval.k]
    hits = [doc_id for doc_id in ranked if doc_id in relevant]
    first_rank = next((index for index, doc_id in enumerate(ranked, 1) if doc_id in relevant), None)
    cited = set(cited_document_ids or [])
    retrieved = set(ranked)
    correct_citations = cited & relevant
    return {
        "case_id": case.case_id,
        "recall_at_k": round(len(set(hits)) / len(relevant), 4),
        "precision_at_k": round(len(hits) / len(ranked), 4) if ranked else 0.0,
        "mrr": round(1 / first_rank, 4) if first_rank else 0.0,
        "citation_coverage": round(len(correct_citations) / len(relevant), 4),
        "citation_correctness": round(len(correct_citations) / len(cited), 4) if cited else 0.0,
        "unknown_citations": sorted(cited - retrieved),
    }
