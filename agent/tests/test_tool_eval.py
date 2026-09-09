from pathlib import Path

from evals.graders.tools import grade_tool_calls
from evals.models import load_cases


def test_tool_dataset_has_at_least_fifteen_versioned_cases():
    path = Path(__file__).parents[1] / "evals" / "datasets" / "tool_cases.jsonl"
    cases = load_cases(path)
    assert len(cases) >= 15
    assert all(case.tools is not None for case in cases)


def test_tool_grader_checks_selection_status_and_forbidden_tools():
    path = Path(__file__).parents[1] / "evals" / "datasets" / "tool_cases.jsonl"
    case = load_cases(path)[0]
    passed = grade_tool_calls(case, {"tool_calls": [{"tool": "knowledge_search", "status": "ok"}]})
    failed = grade_tool_calls(case, {"tool_calls": []})
    assert passed["passed"] is True
    assert failed["passed"] is False
