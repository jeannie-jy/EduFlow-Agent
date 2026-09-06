"""Cross-process operational metrics derived from durable PostgreSQL state."""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return round(ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)], 2)


def _status_counts(rows: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[str(row.status)] += 1
    return dict(sorted(counts.items()))


async def operational_metrics_snapshot(
    session: AsyncSession, *, window_hours: int = 24
) -> dict[str, Any]:
    """Aggregate low-cardinality metrics shared by API and worker processes."""
    from db.models import (
        BackgroundJob,
        ExportJobModel,
        SSEStream,
        ToolCallTrace,
        WorkflowNodeRun,
        WorkflowRun,
    )

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=window_hours)
    workflow_rows = list(
        (
            await session.scalars(
                select(WorkflowRun)
                .where(WorkflowRun.started_at >= cutoff)
                .order_by(WorkflowRun.started_at.desc())
                .limit(5000)
            )
        ).all()
    )
    node_rows = list(
        (
            await session.scalars(
                select(WorkflowNodeRun)
                .where(WorkflowNodeRun.started_at >= cutoff)
                .order_by(WorkflowNodeRun.started_at.desc())
                .limit(20_000)
            )
        ).all()
    )
    tool_rows = list(
        (
            await session.scalars(
                select(ToolCallTrace)
                .where(ToolCallTrace.created_at >= cutoff)
                .order_by(ToolCallTrace.created_at.desc())
                .limit(20_000)
            )
        ).all()
    )
    background_rows = list(
        (
            await session.scalars(
                select(BackgroundJob)
                .where(BackgroundJob.created_at >= cutoff)
                .order_by(BackgroundJob.created_at.desc())
                .limit(10_000)
            )
        ).all()
    )
    export_rows = list(
        (
            await session.scalars(
                select(ExportJobModel)
                .where(ExportJobModel.created_at >= cutoff)
                .order_by(ExportJobModel.created_at.desc())
                .limit(10_000)
            )
        ).all()
    )
    stream_rows = list(
        (
            await session.scalars(
                select(SSEStream)
                .where(SSEStream.created_at >= cutoff)
                .order_by(SSEStream.created_at.desc())
                .limit(10_000)
            )
        ).all()
    )

    completed_workflow_durations = [
        (row.completed_at - row.started_at).total_seconds() * 1000
        for row in workflow_rows
        if row.completed_at is not None and row.started_at is not None
    ]
    successful_workflows = sum(row.status == "succeeded" for row in workflow_rows)
    terminal_workflows = sum(
        row.status in {"succeeded", "failed"} for row in workflow_rows
    )

    nodes: dict[str, dict[str, float | int]] = {}
    for row in node_rows:
        bucket = nodes.setdefault(
            str(row.node_name),
            {
                "runs": 0,
                "errors": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "estimated_cost_usd": 0.0,
            },
        )
        bucket["runs"] += 1
        bucket["errors"] += int(row.status == "failed")
        bucket["input_tokens"] += int(row.input_tokens or 0)
        bucket["output_tokens"] += int(row.output_tokens or 0)
        bucket["estimated_cost_usd"] = round(
            float(bucket["estimated_cost_usd"]) + float(row.estimated_cost_usd or 0), 6
        )

    tools: dict[str, dict[str, float | int]] = {}
    tool_durations: dict[str, list[float]] = defaultdict(list)
    for row in tool_rows:
        bucket = tools.setdefault(str(row.tool_name), {"calls": 0, "errors": 0})
        bucket["calls"] += 1
        bucket["errors"] += int(row.status != "ok")
        tool_durations[str(row.tool_name)].append(float(row.duration_ms or 0))
    for name, bucket in tools.items():
        bucket["duration_ms_p95"] = _p95(tool_durations[name])

    queued_jobs = [
        row
        for row in [*background_rows, *export_rows]
        if row.status in {"queued", "retry_wait"}
    ]
    oldest_wait_seconds = max(
        (
            (now - row.created_at).total_seconds()
            for row in queued_jobs
            if row.created_at
        ),
        default=0,
    )
    terminal_exports = [
        row for row in export_rows if row.status in {"completed", "failed", "cancelled"}
    ]
    completed_exports = [row for row in terminal_exports if row.status == "completed"]
    export_durations = [
        (row.completed_at - row.created_at).total_seconds() * 1000
        for row in terminal_exports
        if row.completed_at is not None and row.created_at is not None
    ]

    return {
        "scope": "database",
        "window_hours": window_hours,
        "generated_at": now.isoformat(),
        "workflows": {
            "status": _status_counts(workflow_rows),
            "success_rate": round(successful_workflows / terminal_workflows, 6)
            if terminal_workflows
            else 0,
            "terminal_runs": terminal_workflows,
            "duration_ms_p95": _p95(completed_workflow_durations),
            "input_tokens": sum(int(row.input_tokens or 0) for row in workflow_rows),
            "output_tokens": sum(int(row.output_tokens or 0) for row in workflow_rows),
            "estimated_cost_usd": round(
                sum(float(row.estimated_cost_usd or 0) for row in workflow_rows), 6
            ),
        },
        "nodes": dict(sorted(nodes.items())),
        "tools": dict(sorted(tools.items())),
        "background_jobs": {"status": _status_counts(background_rows)},
        "export_jobs": {
            "status": _status_counts(export_rows),
            "terminal_jobs": len(terminal_exports),
            "success_rate": round(len(completed_exports) / len(terminal_exports), 6)
            if terminal_exports
            else 0,
            "duration_ms_p95": _p95(export_durations),
        },
        "queue": {
            "depth": len(queued_jobs),
            "oldest_wait_seconds": round(max(oldest_wait_seconds, 0), 2),
        },
        "sse": {"status": _status_counts(stream_rows)},
    }


def prometheus_text(snapshot: dict[str, Any]) -> str:
    """Render the stable operational subset in Prometheus exposition format."""
    lines = ["# TYPE eduflow_workflows_total gauge"]
    workflows = snapshot.get("workflows", {})
    for status, value in workflows.get("status", {}).items():
        lines.append(f'eduflow_workflows_total{{status="{status}"}} {value}')
    lines.extend(
        [
            "# TYPE eduflow_workflow_success_ratio gauge",
            f"eduflow_workflow_success_ratio {workflows.get('success_rate', 0)}",
            "# TYPE eduflow_workflows_terminal gauge",
            f"eduflow_workflows_terminal {workflows.get('terminal_runs', 0)}",
            "# TYPE eduflow_workflow_duration_p95_ms gauge",
            f"eduflow_workflow_duration_p95_ms {workflows.get('duration_ms_p95', 0)}",
            "# TYPE eduflow_queue_depth gauge",
            f"eduflow_queue_depth {snapshot.get('queue', {}).get('depth', 0)}",
            "# TYPE eduflow_queue_oldest_wait_seconds gauge",
            f"eduflow_queue_oldest_wait_seconds {snapshot.get('queue', {}).get('oldest_wait_seconds', 0)}",
            "# TYPE eduflow_workflow_estimated_cost_usd gauge",
            f"eduflow_workflow_estimated_cost_usd {workflows.get('estimated_cost_usd', 0)}",
            "# TYPE eduflow_workflow_tokens gauge",
            f'eduflow_workflow_tokens{{direction="input"}} {workflows.get("input_tokens", 0)}',
            f'eduflow_workflow_tokens{{direction="output"}} {workflows.get("output_tokens", 0)}',
        ]
    )
    for name, values in snapshot.get("nodes", {}).items():
        lines.append(
            f'eduflow_node_runs_total{{node="{name}"}} {values.get("runs", 0)}'
        )
        lines.append(
            f'eduflow_node_errors_total{{node="{name}"}} {values.get("errors", 0)}'
        )
    for name, values in snapshot.get("tools", {}).items():
        lines.append(
            f'eduflow_tool_calls_total{{tool="{name}"}} {values.get("calls", 0)}'
        )
        lines.append(
            f'eduflow_tool_errors_total{{tool="{name}"}} {values.get("errors", 0)}'
        )
        lines.append(
            f'eduflow_tool_duration_p95_ms{{tool="{name}"}} '
            f"{values.get('duration_ms_p95', 0)}"
        )
    for status, value in snapshot.get("sse", {}).get("status", {}).items():
        lines.append(f'eduflow_sse_streams_total{{status="{status}"}} {value}')
    for queue_name in ("background_jobs", "export_jobs"):
        for status, value in snapshot.get(queue_name, {}).get("status", {}).items():
            lines.append(
                f'eduflow_jobs_total{{queue="{queue_name}",status="{status}"}} {value}'
            )
    exports = snapshot.get("export_jobs", {})
    lines.append(f"eduflow_export_success_ratio {exports.get('success_rate', 0)}")
    lines.append(f"eduflow_export_duration_p95_ms {exports.get('duration_ms_p95', 0)}")
    return "\n".join(lines) + "\n"
