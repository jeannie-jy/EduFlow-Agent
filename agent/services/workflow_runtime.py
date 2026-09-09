"""Shared workflow execution primitives used by every compatibility entrypoint."""

from __future__ import annotations

from typing import Any

from agents.state import AgentState
from agents.workflow_policy import needs_reflection


async def run_quality_reflection_cycle(state: AgentState) -> list[dict[str, Any]]:
    """Run the canonical Quality -> Reflection -> Quality loop in place."""
    from agents.nodes import quality_node, reflection_node

    events: list[dict[str, Any]] = []
    while True:
        events.append({"phase": "quality", "message": "正在校验质量...", "pct": 75})
        state.update(await quality_node(state))
        report = state.get("quality_report", {})
        events.append({
            "phase": "validating",
            "message": f"质量校验完成 (score={report.get('overall_score', 1.0):.2f})",
            "pct": 90,
            "quality_report": report,
        })
        if not needs_reflection(state):
            return events
        round_number = state.get("reflection_count", 0) + 1
        events.append({
            "phase": "reflection",
            "message": f"正在修订 (第 {round_number} 次)...",
            "pct": 85,
        })
        state.update(await reflection_node(state))
