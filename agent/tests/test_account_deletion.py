"""Account deletion must not orphan non-relational user data."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.account_deletion import _purge_runtime_state


@pytest.mark.asyncio
async def test_runtime_cleanup_failure_is_retried_without_skipping_other_stores():
    redis = MagicMock()
    redis.delete.side_effect = ConnectionError("redis unavailable")
    delete_thread = AsyncMock()
    graph = SimpleNamespace(checkpointer=SimpleNamespace(adelete_thread=delete_thread))

    with (
        patch("api.export._get_redis", new=AsyncMock(return_value=redis)),
        patch("agents.graph.get_graph_async", new=AsyncMock(return_value=graph)),
        pytest.raises(RuntimeError, match="cleanup is incomplete"),
    ):
        await _purge_runtime_state(["project-1"], ["export-1"], ["feedback:job-1"])

    delete_thread.assert_any_await("project-1")
    delete_thread.assert_any_await("feedback:job-1")


@pytest.mark.asyncio
async def test_runtime_cleanup_accepts_ephemeral_saver_without_delete_api():
    graph = SimpleNamespace(checkpointer=object())

    with (
        patch("api.export._get_redis", new=AsyncMock(return_value=None)),
        patch("agents.graph.get_graph_async", new=AsyncMock(return_value=graph)),
    ):
        await _purge_runtime_state(["project-1"], [], [])


@pytest.mark.asyncio
async def test_runtime_cleanup_requires_redis_when_export_state_exists():
    graph = SimpleNamespace(checkpointer=object())

    with (
        patch("api.export._get_redis", new=AsyncMock(return_value=None)),
        patch("agents.graph.get_graph_async", new=AsyncMock(return_value=graph)),
        pytest.raises(RuntimeError, match="cleanup is incomplete"),
    ):
        await _purge_runtime_state([], ["export-1"], [])
