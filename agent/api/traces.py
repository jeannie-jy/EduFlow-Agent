"""Owner-scoped workflow trace inspection endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import parse_project_id
from db.database import get_readonly_session
from db.models import ToolCallTrace, WorkflowNodeRun, WorkflowRun

router = APIRouter(prefix="/projects", tags=["traces"])


def _run_payload(run: WorkflowRun) -> dict:
    return {
        "id": str(run.id),
        "project_id": str(run.project_id),
        "request_id": run.request_id,
        "thread_id": run.thread_id,
        "entrypoint": run.entrypoint,
        "status": run.status,
        "input_tokens": run.input_tokens,
        "output_tokens": run.output_tokens,
        "estimated_cost_usd": run.estimated_cost_usd,
        "error_class": run.error_class,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
    }


@router.get("/{project_id}/workflow-runs")
async def list_workflow_runs(
    project_id: str,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    session: AsyncSession = Depends(get_readonly_session),
) -> dict:
    rows = await session.scalars(
        select(WorkflowRun)
        .where(WorkflowRun.project_id == parse_project_id(project_id))
        .order_by(WorkflowRun.started_at.desc())
        .limit(limit)
    )
    return {"items": [_run_payload(row) for row in rows.all()]}


@router.get("/{project_id}/workflow-runs/{run_id}")
async def get_workflow_run(
    project_id: str,
    run_id: str,
    session: AsyncSession = Depends(get_readonly_session),
) -> dict:
    try:
        parsed_run_id = uuid.UUID(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Workflow run not found") from exc
    run = await session.get(WorkflowRun, parsed_run_id)
    if run is None or run.project_id != parse_project_id(project_id):
        raise HTTPException(status_code=404, detail="Workflow run not found")
    rows = await session.scalars(
        select(WorkflowNodeRun)
        .where(WorkflowNodeRun.workflow_run_id == run.id)
        .order_by(WorkflowNodeRun.started_at.asc())
    )
    nodes = rows.all()
    node_ids = [node.id for node in nodes]
    tool_rows = []
    if node_ids:
        tool_rows = (await session.scalars(
            select(ToolCallTrace)
            .where(ToolCallTrace.workflow_node_run_id.in_(node_ids))
            .order_by(ToolCallTrace.created_at.asc())
        )).all()
    tools_by_node: dict[uuid.UUID, list[ToolCallTrace]] = {}
    for tool in tool_rows:
        tools_by_node.setdefault(tool.workflow_node_run_id, []).append(tool)
    payload = _run_payload(run)
    payload["nodes"] = [
        {
            "id": str(node.id),
            "node_name": node.node_name,
            "status": node.status,
            "model": node.model,
            "endpoint": node.endpoint,
            "prompt_version": node.prompt_version,
            "input_tokens": node.input_tokens,
            "output_tokens": node.output_tokens,
            "estimated_cost_usd": node.estimated_cost_usd,
            "retry_count": node.retry_count,
            "structured_parse_success": node.structured_parse_success,
            "error_class": node.error_class,
            "attributes": node.attributes,
            "started_at": node.started_at,
            "completed_at": node.completed_at,
            "duration_ms": node.duration_ms,
            "tool_calls": [{
                "tool_call_id": tool.tool_call_id,
                "tool": tool.tool_name,
                "version": tool.tool_version,
                "status": tool.status,
                "arguments_summary": tool.arguments_summary,
                "result_summary": tool.result_summary,
                "error_code": tool.error_code,
                "duration_ms": tool.duration_ms,
                "created_at": tool.created_at,
            } for tool in tools_by_node.get(node.id, [])],
        }
        for node in nodes
    ]
    return payload
