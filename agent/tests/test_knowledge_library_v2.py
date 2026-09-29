"""Regression tests for the gated v2 knowledge path."""

from __future__ import annotations

import uuid
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.knowledge_library import _vector_literal, search_library, split_text
from services.retrieval import retrieve_knowledge_context
from services.knowledge_service import stable_source_key


def test_split_text_preserves_long_material_without_truncation():
    content = "x" * 150_000
    chunks = split_text(content)
    assert len(chunks) > 100
    assert chunks[-1]["locator"].endswith("150000")
    assert chunks[0]["content"].startswith("x")


def test_embedding_dimension_is_fixed_to_index_schema():
    with pytest.raises(ValueError, match="1024"):
        _vector_literal([0.1] * 1536)


def test_legacy_seed_has_22_distinct_stable_ids():
    seed_path = Path(__file__).resolve().parents[1] / "data" / "seed_knowledge.json"
    entries = json.loads(seed_path.read_text(encoding="utf-8"))
    keys = [stable_source_key(row["concept"], row.get("subject")) for row in entries]
    assert len(keys) == 22
    assert len(set(keys)) == 22
    assert "algo-dijkstra-constraints" in keys


@pytest.mark.asyncio
async def test_empty_query_never_returns_arbitrary_seed():
    session = AsyncMock()
    assert await search_library(session, "   ") == []
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_teacher_scope_is_enforced_in_database_query():
    session = AsyncMock()
    result = MagicMock()
    result.mappings.return_value.all.return_value = []
    session.execute.return_value = result
    owner_id, project_id = uuid.uuid4(), uuid.uuid4()
    with patch("services.knowledge_library._canonical_credential_available", return_value=False):
        rows = await search_library(session, "二分查找", owner_id=owner_id, project_id=project_id)
    assert rows == []
    statement, params = session.execute.await_args.args
    sql = str(statement)
    assert "s.owner_id = :owner_id" in sql
    assert "pks.project_id = :project_id" in sql
    assert params["owner_id"] == owner_id
    assert params["project_id"] == project_id


@pytest.mark.asyncio
async def test_project_search_requires_owner():
    with pytest.raises(PermissionError):
        await search_library(AsyncMock(), "排序", project_id=uuid.uuid4())


@pytest.mark.asyncio
async def test_v2_retrieval_preserves_stable_source_and_precise_locator():
    context = AsyncMock()
    context.__aenter__.return_value = AsyncMock()
    search = AsyncMock(return_value=[{
        "id": "chunk-1", "chunk_id": "chunk-1", "source_key": "algo_binary_search",
        "concept": "二分查找", "content": "有序数组", "similarity": 0.91,
        "version": "2026.1", "section": "查找", "locator": "section:2",
        "scope": "builtin", "source_url": "https://example.org/search",
    }])
    settings = type("Settings", (), {
        "knowledge_v2_enabled": True, "knowledge_search_top_k": 5,
        "retrieval_context_max_chars": 2000,
    })()
    with (
        patch("db.database.async_session_factory", return_value=context),
        patch("services.knowledge_library.search_library", search),
        patch("services.retrieval.get_settings", return_value=settings),
    ):
        result = await retrieve_knowledge_context("二分查找")
    source = result["sources"][0]
    assert source["source_id"] == "algo_binary_search"
    assert source["chunk_id"] == "chunk-1"
    assert source["version"] == "2026.1"
    assert source["locator"] == "section:2"
