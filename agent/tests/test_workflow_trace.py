"""Durable workflow tracing tests."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from db.models import Project, ToolCallTrace, WorkflowNodeRun, WorkflowRun
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker


def test_safe_node_attributes_records_module_batch_without_content():
    from services.workflow_trace import _safe_node_attributes

    attributes = _safe_node_attributes({
        "module_outputs": {"frames": {"secret": "not persisted"}, "quiz": {}},
        "module_errors": {"video": "provider secret"},
    })

    assert attributes == {
        "module_count": 3,
        "module_ids": ["frames", "quiz", "video"],
    }

# Reuse the repository's PostgreSQL-to-SQLite metadata adapter before the
# shared test_db fixture creates tables.
from tests.test_db_integration import _make_sqlite_compatible

_make_sqlite_compatible()


@pytest.mark.asyncio
async def test_trace_persists_sanitized_node_usage(test_db):
    from services.telemetry import record_gateway_retry, record_llm_call
    from services.workflow_trace import (
        finish_node_trace,
        start_node_trace,
        workflow_trace_scope,
    )

    project_id = uuid.uuid4()
    test_db.add(Project(id=project_id, title="Trace project"))
    await test_db.commit()
    factory = async_sessionmaker(test_db.bind, expire_on_commit=False)
    graph_run_id = uuid.uuid4()

    with patch("db.database.async_session_factory", factory):
        async with workflow_trace_scope(
            project_id=str(project_id), thread_id="thread-1", entrypoint="planner"
        ):
            await start_node_trace("knowledge", graph_run_id)
            record_llm_call(
                input_tokens=100,
                output_tokens=25,
                duration_ms=12,
                model="model-a",
                operation="structured",
                estimated_cost_usd=0.01,
                endpoint="https://user:password@provider.invalid/v1?api_key=secret",
                prompt_version="abc123",
            )
            record_gateway_retry(operation="structured", reason="TimeoutError")
            await finish_node_trace(
                graph_run_id,
                output={
                    "knowledge_graph": {
                        "sources": [
                            {"source_id": "doc-1", "score": 0.9, "content": "secret"}
                        ]
                    }
                },
            )

    run = (await test_db.scalars(select(WorkflowRun))).one()
    node = (await test_db.scalars(select(WorkflowNodeRun))).one()
    assert run.status == "succeeded"
    assert run.input_tokens == 100
    assert run.output_tokens == 25
    assert run.estimated_cost_usd == pytest.approx(0.01)
    assert node.node_name == "knowledge"
    assert node.model == "model-a"
    assert node.endpoint == "https://provider.invalid/v1"
    assert node.prompt_version == "abc123"
    assert node.retry_count == 1
    assert node.structured_parse_success is True
    assert node.attributes == {
        "retrieval_sources": [{"source_id": "doc-1", "score": 0.9}],
        "retrieval_context_chars": 6,
    }
    assert "secret" not in str(node.attributes)


@pytest.mark.asyncio
async def test_trace_api_hides_run_from_another_project(test_db):
    from api.traces import get_workflow_run
    from fastapi import HTTPException

    first = uuid.uuid4()
    second = uuid.uuid4()
    run_id = uuid.uuid4()
    test_db.add_all([
        Project(id=first, title="First"),
        Project(id=second, title="Second"),
        WorkflowRun(
            id=run_id,
            project_id=first,
            request_id="request-1",
            thread_id="thread-1",
            entrypoint="planner",
            status="succeeded",
        ),
    ])
    await test_db.commit()

    with pytest.raises(HTTPException) as exc:
        await get_workflow_run(str(second), str(run_id), test_db)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_tool_trace_hashes_arguments_and_api_returns_summaries(test_db):
    from api.traces import get_workflow_run
    from services.workflow_trace import (
        finish_node_trace,
        record_tool_call_trace,
        start_node_trace,
        workflow_trace_scope,
    )

    project_id = uuid.uuid4()
    test_db.add(Project(id=project_id, title="Tool trace project"))
    await test_db.commit()
    factory = async_sessionmaker(test_db.bind, expire_on_commit=False)
    graph_run_id = uuid.uuid4()
    secret_query = "private course query"

    with patch("db.database.async_session_factory", factory):
        async with workflow_trace_scope(
            project_id=str(project_id), thread_id="thread-tools", entrypoint="planner"
        ):
            await start_node_trace("knowledge", graph_run_id)
            await record_tool_call_trace(
                {"query": secret_query, "top_k": 3},
                {
                    "tool_call_id": "call-tool-1",
                    "tool": "knowledge_search",
                    "version": "1.0",
                    "status": "ok",
                    "data": {"selected_count": 2, "sources": [{"content": "secret"}]},
                    "duration_ms": 4.2,
                    "truncated": False,
                    "error_code": None,
                },
            )
            await finish_node_trace(graph_run_id, output={"tool_calls": []})

    trace = (await test_db.scalars(select(ToolCallTrace))).one()
    assert secret_query not in str(trace.arguments_summary)
    run = (await test_db.scalars(select(WorkflowRun))).one()
    payload = await get_workflow_run(str(project_id), str(run.id), test_db)
    tool_payload = payload["nodes"][0]["tool_calls"][0]
    assert tool_payload["tool"] == "knowledge_search"
    assert tool_payload["result_summary"]["selected_count"] == 2
    assert "secret" not in str(tool_payload)


@pytest.mark.asyncio
async def test_traced_graph_invocation_observes_node_events():
    from contextlib import asynccontextmanager
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock

    from services.workflow_trace import invoke_graph_traced

    graph = MagicMock()

    async def events(*_args, **_kwargs):
        yield {"event": "on_chain_start", "name": "reflection", "run_id": "n1"}
        yield {
            "event": "on_chain_end",
            "name": "reflection",
            "run_id": "n1",
            "data": {"output": {"dsl": {"frames": []}}},
        }

    graph.astream_events = events
    graph.aget_state = AsyncMock(
        return_value=SimpleNamespace(values={"dsl": {"frames": []}})
    )
    observed = AsyncMock()

    @asynccontextmanager
    async def scope(**_kwargs):
        yield MagicMock()

    with (
        patch("services.workflow_trace.workflow_trace_scope", new=scope),
        patch("services.workflow_trace.observe_graph_trace_event", new=observed),
    ):
        result = await invoke_graph_traced(
            graph,
            {"workflow_entry": "reflection"},
            {"configurable": {"thread_id": "feedback:1"}},
            project_id=str(uuid.uuid4()),
            entrypoint="reflection",
        )

    assert result == {"dsl": {"frames": []}}
    assert observed.await_count == 2
