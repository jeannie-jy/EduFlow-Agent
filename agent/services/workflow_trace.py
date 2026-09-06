"""Durable, sanitized workflow traces backed by PostgreSQL.

Tracing is deliberately best-effort: observability failures are logged but never
change the user-visible workflow result. Prompt text and material content are not
stored.
"""

from __future__ import annotations

import contextvars
import hashlib
import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from services.telemetry import request_id_var

logger = logging.getLogger(__name__)


@dataclass
class NodeUsage:
    node_id: uuid.UUID
    node_name: str
    started: float = field(default_factory=time.perf_counter)
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    retry_count: int = 0
    model: str | None = None
    endpoint: str | None = None
    prompt_version: str | None = None


@dataclass
class WorkflowTraceContext:
    run_id: uuid.UUID
    enabled: bool
    status: str = "succeeded"
    nodes: dict[str, NodeUsage] = field(default_factory=dict)
    active_node_key: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0


_trace_var: contextvars.ContextVar[WorkflowTraceContext | None] = contextvars.ContextVar(
    "workflow_trace", default=None
)
TRACE_NODE_NAMES = {
    "planner", "knowledge", "coder", "quality", "reflection", "modules"
}


@asynccontextmanager
async def workflow_trace_scope(
    *, project_id: str, thread_id: str, entrypoint: str
) -> AsyncIterator[WorkflowTraceContext]:
    context = WorkflowTraceContext(run_id=uuid.uuid4(), enabled=False)
    try:
        from api.deps import parse_project_id
        from db.database import async_session_factory
        from db.models import WorkflowRun
        from sqlalchemy import select

        parsed_project_id = parse_project_id(project_id)
        async with async_session_factory() as session:
            if entrypoint == "resume":
                previous = await session.scalars(
                    select(WorkflowRun).where(
                        WorkflowRun.project_id == parsed_project_id,
                        WorkflowRun.thread_id == thread_id[:300],
                        WorkflowRun.status == "waiting_approval",
                    )
                )
                for row in previous.all():
                    row.status = "resumed"
                    row.completed_at = datetime.now(timezone.utc)
            session.add(WorkflowRun(
                id=context.run_id,
                project_id=parsed_project_id,
                request_id=request_id_var.get()[:100],
                thread_id=thread_id[:300],
                entrypoint=entrypoint[:50],
                status="running",
            ))
            await session.commit()
        context.enabled = True
    except Exception:
        logger.exception("workflow trace start failed")

    token = _trace_var.set(context)
    try:
        yield context
    except BaseException as exc:
        context.status = "failed"
        await _finish_workflow(context, type(exc).__name__)
        raise
    else:
        await _finish_workflow(context, None)
    finally:
        _trace_var.reset(token)


def set_workflow_trace_status(status: str) -> None:
    context = _trace_var.get()
    if context is not None:
        context.status = status[:50]


def current_trace_identifiers() -> tuple[str | None, str | None]:
    """Expose trace IDs to server-created execution contexts, never to tool args."""
    context = _trace_var.get()
    if context is None:
        return None, None
    usage = context.nodes.get(context.active_node_key or "")
    return str(context.run_id), str(usage.node_id) if usage is not None else None


async def observe_graph_trace_event(event: dict[str, Any]) -> None:
    """Persist one LangGraph v2 lifecycle event when it represents a workflow node."""
    event_type = event.get("event", "")
    node_name = event.get("name", "")
    if node_name not in TRACE_NODE_NAMES:
        return
    if event_type == "on_chain_start":
        await start_node_trace(node_name, event.get("run_id"))
    elif event_type == "on_chain_end":
        await finish_node_trace(
            event.get("run_id"), output=event.get("data", {}).get("output")
        )
    elif event_type == "on_chain_error":
        error = event.get("data", {}).get("error")
        await finish_node_trace(
            event.get("run_id"),
            status="failed",
            error_class=type(error).__name__ if error is not None else "UnknownError",
        )


async def invoke_graph_traced(
    graph: Any,
    graph_input: Any,
    config: dict[str, Any],
    *,
    project_id: str,
    entrypoint: str,
) -> dict[str, Any]:
    """Invoke a graph through its event stream so workers get the same trace detail."""
    thread_id = str(config.get("configurable", {}).get("thread_id", project_id))
    async with workflow_trace_scope(
        project_id=project_id,
        thread_id=thread_id,
        entrypoint=entrypoint,
    ):
        async for event in graph.astream_events(graph_input, config=config, version="v2"):
            await observe_graph_trace_event(event)
        final_state = await graph.aget_state(config)
        values = getattr(final_state, "values", None)
        return dict(values) if isinstance(values, dict) else {}


async def start_node_trace(node_name: str, graph_run_id: Any) -> None:
    context = _trace_var.get()
    if context is None or not context.enabled:
        return
    graph_key = str(graph_run_id or uuid.uuid4())[:100]
    usage = NodeUsage(node_id=uuid.uuid4(), node_name=node_name)
    context.nodes[graph_key] = usage
    context.active_node_key = graph_key
    try:
        from db.database import async_session_factory
        from db.models import WorkflowNodeRun

        async with async_session_factory() as session:
            session.add(WorkflowNodeRun(
                id=usage.node_id,
                workflow_run_id=context.run_id,
                graph_run_id=graph_key,
                node_name=node_name[:100],
                status="running",
            ))
            await session.commit()
    except Exception:
        logger.exception("workflow node trace start failed: node=%s", node_name)


async def finish_node_trace(
    graph_run_id: Any,
    *,
    status: str = "succeeded",
    error_class: str | None = None,
    output: Any = None,
) -> None:
    context = _trace_var.get()
    if context is None or not context.enabled:
        return
    graph_key = str(graph_run_id)[:100]
    usage = context.nodes.get(graph_key)
    if usage is None:
        return
    if context.active_node_key == graph_key:
        context.active_node_key = None
    try:
        from db.database import async_session_factory
        from db.models import WorkflowNodeRun

        async with async_session_factory() as session:
            row = await session.get(WorkflowNodeRun, usage.node_id)
            if row is not None:
                row.status = status[:50]
                row.completed_at = datetime.now(timezone.utc)
                row.duration_ms = (time.perf_counter() - usage.started) * 1000
                row.model = usage.model
                row.endpoint = usage.endpoint
                row.prompt_version = usage.prompt_version
                row.input_tokens = usage.input_tokens
                row.output_tokens = usage.output_tokens
                row.estimated_cost_usd = usage.estimated_cost_usd
                row.retry_count = usage.retry_count
                row.structured_parse_success = (
                    status == "succeeded"
                    if usage.node_name in {
                        "planner", "knowledge", "coder", "quality", "reflection"
                    }
                    else None
                )
                row.error_class = error_class[:100] if error_class else None
                row.attributes = _safe_node_attributes(output)
                await session.commit()
    except Exception:
        logger.exception("workflow node trace finish failed")


def record_trace_llm_call(
    *, input_tokens: int, output_tokens: int, estimated_cost_usd: float,
    model: str, endpoint: str | None, prompt_version: str | None,
) -> None:
    context = _trace_var.get()
    if context is None:
        return
    context.input_tokens += max(input_tokens, 0)
    context.output_tokens += max(output_tokens, 0)
    context.estimated_cost_usd += max(estimated_cost_usd, 0)
    usage = context.nodes.get(context.active_node_key or "")
    if usage is not None:
        usage.input_tokens += max(input_tokens, 0)
        usage.output_tokens += max(output_tokens, 0)
        usage.estimated_cost_usd += max(estimated_cost_usd, 0)
        usage.model = model[:200]
        usage.endpoint = _sanitize_endpoint(endpoint)
        usage.prompt_version = prompt_version[:100] if prompt_version else None


def record_trace_retry() -> None:
    context = _trace_var.get()
    if context is None:
        return
    usage = context.nodes.get(context.active_node_key or "")
    if usage is not None:
        usage.retry_count += 1


async def record_tool_call_trace(
    arguments: dict[str, Any], result: dict[str, Any]
) -> None:
    """Persist one tool call without storing queries or returned content."""
    context = _trace_var.get()
    if context is None or not context.enabled:
        return
    usage = context.nodes.get(context.active_node_key or "")
    if usage is None:
        return
    from db.database import async_session_factory
    from db.models import ToolCallTrace

    def summarize(value: Any) -> Any:
        if isinstance(value, str):
            return {
                "type": "string",
                "chars": len(value),
                "sha256": hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:16],
            }
        if isinstance(value, list):
            return {"type": "array", "count": len(value)}
        if isinstance(value, (int, float, bool)) or value is None:
            return value
        if isinstance(value, dict):
            return {"type": "object", "keys": sorted(map(str, value.keys()))[:30]}
        return {"type": type(value).__name__}

    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    result_summary = {
        "keys": sorted(data.keys())[:30],
        "selected_count": data.get("selected_count"),
        "found_count": data.get("found_count"),
        "truncated": result.get("truncated", False),
    }
    async with async_session_factory() as session:
        session.add(ToolCallTrace(
            id=uuid.uuid4(),
            workflow_node_run_id=usage.node_id,
            tool_call_id=str(result.get("tool_call_id") or "")[:200],
            tool_name=str(result.get("tool") or "")[:100],
            tool_version=str(result.get("version"))[:50] if result.get("version") else None,
            status=str(result.get("status") or "error")[:50],
            arguments_summary={str(key): summarize(value) for key, value in arguments.items()},
            result_summary=result_summary,
            error_code=str(result.get("error_code"))[:100] if result.get("error_code") else None,
            duration_ms=float(result.get("duration_ms") or 0),
        ))
        await session.commit()


async def _finish_workflow(
    context: WorkflowTraceContext, error_class: str | None
) -> None:
    if not context.enabled:
        return
    try:
        from db.database import async_session_factory
        from db.models import WorkflowRun

        async with async_session_factory() as session:
            row = await session.get(WorkflowRun, context.run_id)
            if row is not None:
                row.status = context.status
                row.input_tokens = context.input_tokens
                row.output_tokens = context.output_tokens
                row.estimated_cost_usd = context.estimated_cost_usd
                row.error_class = error_class[:100] if error_class else None
                if context.status != "waiting_approval":
                    row.completed_at = datetime.now(timezone.utc)
                await session.commit()
    except Exception:
        logger.exception("workflow trace finish failed")


def _safe_node_attributes(output: Any) -> dict[str, Any] | None:
    if not isinstance(output, dict):
        return None
    result: dict[str, Any] = {}
    if isinstance(output.get("dsl"), dict):
        result["frame_count"] = len(output["dsl"].get("frames", []))
        if output["dsl"].get("artifact_version"):
            result["artifact_version"] = str(output["dsl"]["artifact_version"])[:100]
    if isinstance(output.get("quality_report"), dict):
        report = output["quality_report"]
        result["quality_score"] = report.get("overall_score")
        result["quality_blocking"] = report.get("is_blocking")
    module_outputs = output.get("module_outputs")
    module_errors = output.get("module_errors")
    if isinstance(module_outputs, dict) or isinstance(module_errors, dict):
        module_ids = sorted(
            set(module_outputs if isinstance(module_outputs, dict) else {})
            | set(module_errors if isinstance(module_errors, dict) else {})
        )[:32]
        result["module_count"] = len(module_ids)
        result["module_ids"] = module_ids
    graph = output.get("knowledge_graph")
    if isinstance(graph, dict):
        sources = graph.get("sources", [])
        if isinstance(sources, list):
            result["retrieval_sources"] = [
                {
                    "source_id": source.get("source_id", source.get("id")),
                    "score": source.get("score"),
                }
                for source in sources[:20]
                if isinstance(source, dict)
            ]
            result["retrieval_context_chars"] = sum(
                len(str(source.get("content", source.get("content_text", source.get("excerpt", "")))))
                for source in sources[:20]
                if isinstance(source, dict)
            )
    calls = output.get("tool_calls")
    if isinstance(calls, list):
        result["tool_calls"] = [
            {
                "tool_call_id": call.get("tool_call_id"),
                "tool": call.get("tool"),
                "version": call.get("version"),
                "status": call.get("status"),
                "error_code": call.get("error_code"),
                "duration_ms": call.get("duration_ms"),
            }
            for call in calls[:32]
            if isinstance(call, dict)
        ]
    return result or None


def _sanitize_endpoint(endpoint: str | None) -> str | None:
    if not endpoint:
        return None
    try:
        parsed = urlsplit(endpoint)
        hostname = parsed.hostname or ""
        port = f":{parsed.port}" if parsed.port else ""
        return urlunsplit((parsed.scheme, f"{hostname}{port}", parsed.path, "", ""))[:500]
    except (ValueError, TypeError):
        return "invalid-endpoint"
