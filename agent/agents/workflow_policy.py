"""Single source of truth for workflow routing decisions."""

from __future__ import annotations

from agents.state import AgentState
from config import get_settings


def needs_reflection(state: AgentState) -> bool:
    settings = get_settings()
    report = state.get("quality_report", {})
    return (
        report.get("overall_score", 1.0) < settings.quality_score_threshold
        or bool(report.get("is_blocking", False))
    ) and state.get("reflection_count", 0) < settings.max_reflection_cycles
