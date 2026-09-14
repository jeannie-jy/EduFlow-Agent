"""Deployed environments must use the durable workflow checkpointer."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

import agents.graph as graph_module


@pytest.mark.asyncio
async def test_production_checkpointer_failure_does_not_fall_back_to_memory():
    original = (
        graph_module._graph,
        graph_module._checkpointer,
        graph_module._checkpointer_initialized,
        graph_module._checkpointer_stack,
    )
    graph_module._graph = None
    graph_module._checkpointer = None
    graph_module._checkpointer_initialized = False
    graph_module._checkpointer_stack = None
    settings = SimpleNamespace(
        database_url="postgresql+asyncpg://agent:secret@db/eduflow",
        environment="production",
    )

    try:
        with (
            patch("config.get_settings", return_value=settings),
            patch.object(graph_module, "get_settings", return_value=settings),
            patch(
                "langgraph.checkpoint.postgres.aio.AsyncPostgresSaver.from_conn_string",
                side_effect=ConnectionError("postgres unavailable"),
            ),
            pytest.raises(RuntimeError, match="Persistent Postgres checkpointer"),
        ):
            await graph_module.get_graph_async()
        assert graph_module._checkpointer is None
        assert graph_module._checkpointer_initialized is False
    finally:
        (
            graph_module._graph,
            graph_module._checkpointer,
            graph_module._checkpointer_initialized,
            graph_module._checkpointer_stack,
        ) = original
