"""Deterministic Tool Calling selection and execution-envelope grader."""

from __future__ import annotations

from typing import Any

from evals.models import EvalCase


def grade_tool_calls(case: EvalCase, artifact: dict[str, Any]) -> dict[str, Any]:
    if case.tools is None:
        raise ValueError(f"case has no tool expectation: {case.case_id}")
    calls = artifact.get("tool_calls", [])
    if not isinstance(calls, list):
        calls = []
    names = [str(call.get("tool") or call.get("name") or "") for call in calls if isinstance(call, dict)]
    statuses = [str(call.get("status") or "") for call in calls if isinstance(call, dict)]
    expected = set(case.tools.expected_tools)
    forbidden = set(case.tools.forbidden_tools)
    selected = set(names)
    selection_ok = expected.issubset(selected)
    forbidden_ok = not bool(forbidden & selected)
    no_tool_ok = bool(names) or case.tools.allow_no_tool
    status_ok = all(status in case.tools.expected_statuses for status in statuses)
    budget_ok = len(names) <= case.tools.max_calls
    issues = []
    if not selection_ok:
        issues.append(f"missing expected tools: {sorted(expected - selected)}")
    if not forbidden_ok:
        issues.append(f"forbidden tools selected: {sorted(forbidden & selected)}")
    if not no_tool_ok:
        issues.append("no tool selected when a tool was required")
    if not status_ok:
        issues.append("unexpected tool execution status")
    if not budget_ok:
        issues.append(f"tool call count {len(names)} exceeds {case.tools.max_calls}")
    metrics = {
        "tool_selection_pass": selection_ok,
        "forbidden_tool_pass": forbidden_ok,
        "tool_status_pass": status_ok,
        "tool_budget_pass": budget_ok,
        "tool_call_count": len(names),
    }
    return {
        "case_id": case.case_id,
        "tags": case.tags,
        "passed": all([selection_ok, forbidden_ok, no_tool_ok, status_ok, budget_ok]),
        "metrics": metrics,
        "issues": issues,
    }
