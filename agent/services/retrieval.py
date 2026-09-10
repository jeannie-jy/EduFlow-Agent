"""Retrieval boundary used by the generation workflow.

Retrieved text is data, never instruction. This module gives every chunk a
stable citation envelope before it is exposed to an LLM prompt.
"""

from __future__ import annotations

import logging
from typing import Any

from config import get_settings

logger = logging.getLogger(__name__)


_ABSTENTION_MARKERS = (
    "未收录",
    "私有算法",
    "未知算法",
    "不存在",
    "没有相关",
    "无相关",
    "证据不足",
)


def _is_abstention_intent(topic: str) -> bool:
    """Detect explicit requests to abstain on an unknown/private topic."""
    normalized = " ".join(str(topic or "").split()).casefold()
    return any(marker.casefold() in normalized for marker in _ABSTENTION_MARKERS)


def build_retrieval_queries(topic: str, teaching_plan: dict[str, Any]) -> list[str]:
    """Produce bounded query variants without another paid model call."""
    settings = get_settings()
    candidates = [topic]
    candidates.extend(str(item) for item in teaching_plan.get("objectives", []))
    for step in teaching_plan.get("outline", []):
        if isinstance(step, dict):
            candidates.extend(str(item) for item in step.get("key_points", []))
    unique = []
    for candidate in candidates:
        cleaned = " ".join(candidate.split()).strip()
        if cleaned and cleaned.casefold() not in {item.casefold() for item in unique}:
            unique.append(cleaned)
        if len(unique) >= settings.retrieval_query_count:
            break
    return unique or [topic]


async def retrieve_knowledge_context(
    query: str, *, queries: list[str] | None = None
) -> dict[str, Any]:
    settings = get_settings()
    search_queries = queries or [query]
    # For an explicit unknown/private-topic request, generated objectives are
    # not independent evidence. Searching them can turn a semantic near-match
    # (e.g. a generic DP document) into a false positive and defeat abstention.
    if _is_abstention_intent(query):
        search_queries = [search_queries[0] if search_queries else query]
    try:
        from db.database import async_session_factory
        from services.knowledge_service import search_knowledge_pgvector

        fused: dict[str, dict[str, Any]] = {}
        async with async_session_factory() as session:
            for search_query in search_queries:
                rows = await search_knowledge_pgvector(
                    search_query,
                    top_k=settings.knowledge_search_top_k,
                    session=session,
                )
                for rank, row in enumerate(rows, 1):
                    source_id = str(
                        row.get("source_key")
                        or row.get("id")
                        or row.get("concept")
                        or f"knowledge-{rank}"
                    )
                    entry = fused.setdefault(source_id, {**row, "rrf_score": 0.0, "matched_queries": []})
                    entry["rrf_score"] += 1 / (60 + rank)
                    entry["matched_queries"].append(search_query)
        rows = sorted(fused.values(), key=lambda item: item["rrf_score"], reverse=True)
        # Objectives and key points are useful query expansions, but they can
        # be broader than the user's topic (for example, ``贪心`` can match
        # unrelated graph algorithms). If the primary topic already has
        # evidence, keep only primary hits or documents corroborated by at
        # least two query variants. This preserves RRF while preventing a
        # single noisy expansion from becoming a cited source in the DSL.
        if len(search_queries) > 1:
            primary_hits = [
                row for row in rows if search_queries[0] in row.get("matched_queries", [])
            ]
            if primary_hits:
                rows = [
                    row
                    for row in rows
                    if search_queries[0] in row.get("matched_queries", [])
                    or len(row.get("matched_queries", [])) >= 2
                ]
    except Exception as exc:
        logger.warning("workflow retrieval unavailable; continuing without evidence: %s", exc)
        return {"status": "unavailable", "query": query, "sources": [], "error_type": type(exc).__name__}

    sources = []
    used_chars = 0
    for index, row in enumerate(rows):
        content = str(row.get("content") or "")[:1000]
        if sources and used_chars + len(content) > settings.retrieval_context_max_chars:
            break
        source = {
            "source_id": str(
                row.get("source_key") or row.get("id") or f"knowledge-{index}"
            ),
            "title": str(row.get("concept") or "untitled")[:200],
            "content": content,
            "similarity": float(row.get("similarity") or 0),
            "rrf_score": round(float(row.get("rrf_score") or 0), 6),
            "matched_queries": row.get("matched_queries", []),
            "trust": "retrieved_untrusted",
        }
        sources.append(source)
        used_chars += len(content)
    return {
        "status": "ok" if sources else "no_evidence",
        "query": query,
        "queries": search_queries,
        "candidate_count": len(rows),
        "selected_count": len(sources),
        "context_chars": used_chars,
        "truncated": len(sources) < len(rows),
        "sources": sources,
    }
