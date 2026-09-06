"""Contract tests for the first-party real Tool Calling benchmark adapter."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from evals.generators.live_tools import _bootstrap_fixture, generate_tool_case
from evals.models import EvalCase


@pytest.mark.asyncio
async def test_live_generator_uses_production_runtime_and_reports_usage() -> None:
    case = EvalCase.model_validate(
        {
            "case_id": "tool_live_contract",
            "domain": "database",
            "difficulty": "beginner",
            "topic": "读取指定讲义",
            "expected": {"min_frames": 0, "max_frames": 1},
            "tools": {"expected_tools": ["material_lookup"]},
        }
    )
    project_id = uuid.uuid4()
    material_id = uuid.uuid4()
    runtime = AsyncMock(
        return_value={
            "calls": [{"tool": "material_lookup", "status": "ok"}],
            "content": "done",
            "rounds": 2,
            "exhausted": False,
            "usage": {"input": 1000, "output": 500},
        }
    )
    settings = SimpleNamespace(
        llm_input_cost_per_million=1.0,
        llm_output_cost_per_million=2.0,
    )
    with (
        patch(
            "evals.generators.live_tools._bootstrap_fixture",
            new=AsyncMock(return_value=(project_id, material_id)),
        ),
        patch("services.tool_runtime.run_tool_calling_loop", runtime),
        patch("config.get_settings", return_value=settings),
    ):
        generated = await generate_tool_case(case)

    assert generated["artifact"]["tool_calls"] == [
        {"tool": "material_lookup", "status": "ok"}
    ]
    assert generated["usage"] == {"input": 1000, "output": 500}
    assert generated["cost_usd"] == 0.002
    call = runtime.await_args.kwargs
    assert call["project_id"] == str(project_id)
    assert str(material_id) in call["user_message"]


@pytest.mark.asyncio
async def test_live_generator_rejects_non_tool_case() -> None:
    case = EvalCase.model_validate(
        {
            "case_id": "ordinary_case",
            "domain": "custom",
            "difficulty": "beginner",
            "topic": "普通主题",
            "expected": {"min_frames": 0, "max_frames": 1},
        }
    )
    with pytest.raises(ValueError, match="not a Tool Calling case"):
        await generate_tool_case(case)


@pytest.mark.asyncio
async def test_fixture_bootstrap_requires_explicit_isolation_or_ids() -> None:
    with (
        patch.dict("os.environ", {}, clear=True),
        pytest.raises(RuntimeError, match="isolated evaluation database"),
    ):
        await _bootstrap_fixture()
