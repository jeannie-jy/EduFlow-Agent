"""First-party production LangGraph adapter for the core online benchmark."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from evals.generators.live_workflow import generate_workflow_case
from evals.models import EvalCase


def _case() -> EvalCase:
    return EvalCase.model_validate(
        {
            "case_id": "alg_live_workflow",
            "domain": "algorithm",
            "difficulty": "beginner",
            "topic": "冒泡排序",
            "constraints": {"language": "zh-CN"},
            "materials": [{"type": "text", "content": "相邻元素交换"}],
            "expected": {"min_frames": 1, "max_frames": 8},
        }
    )


@pytest.mark.asyncio
async def test_live_workflow_adapter_uses_production_graph_and_reports_usage():
    generated_state = {
        "dsl": {"topic": "冒泡排序", "frames": [{"frame_id": "f_001"}]},
        "quality_report": {"overall_score": 0.9},
    }
    generate = AsyncMock(
        return_value=(
            generated_state,
            {"input": 120, "output": 80, "total": 200, "cost_usd": 0.0012},
        )
    )
    with patch(
        "services.generate_service.run_generation_sync_with_usage", generate
    ):
        result = await generate_workflow_case(_case())

    assert result["artifact"] == generated_state["dsl"]
    assert result["usage"] == {"input": 120, "output": 80}
    assert result["cost_usd"] == 0.0012
    assert result["metadata"]["quality_report"]["overall_score"] == 0.9
    args = generate.await_args.args
    assert args[1] == "冒泡排序"
    assert generate.await_args.kwargs["constraints"]["eval_case_id"] == "alg_live_workflow"
    assert generate.await_args.kwargs["thread_id"].startswith(
        "eval:alg_live_workflow:"
    )


@pytest.mark.asyncio
async def test_live_workflow_adapter_rejects_missing_dsl():
    with (
        patch(
            "services.generate_service.run_generation_sync_with_usage",
            new=AsyncMock(return_value=({}, {"cost_usd": 0.0})),
        ),
        pytest.raises(TypeError, match="no DSL artifact"),
    ):
        await generate_workflow_case(_case())


@pytest.mark.asyncio
async def test_live_workflow_adapter_rejects_zero_token_provider_fallback():
    """Online reports must not count deterministic fallback as model quality."""
    generated_state = {
        "dsl": {"topic": "冒泡排序", "frames": [{"frame_id": "f_001"}]},
    }
    with (
        patch(
            "services.generate_service.run_generation_sync_with_usage",
            new=AsyncMock(return_value=(generated_state, {"cost_usd": 0.0})),
        ),
        pytest.raises(RuntimeError, match="no candidate LLM tokens"),
    ):
        await generate_workflow_case(_case())


def test_manual_quality_workflow_uses_production_adapter_and_auditable_outputs():
    workflow = (
        Path(__file__).parents[2] / ".github/workflows/online-quality-bench.yml"
    ).read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "evals.generators.live_workflow:generate_workflow_case" in workflow
    assert "EDUFLOW_ALLOW_ONLINE_EVAL=1" in workflow
    assert "--dataset evals/datasets/eduflowbench_v1.jsonl" in workflow
    assert "embedding_endpoint:" in workflow
    assert "embedding_model:" in workflow
    assert "embedding_dimension:" in workflow
    assert "EMBEDDING_ENDPOINT: ${{ inputs.embedding_endpoint }}" in workflow
    assert "EMBEDDING_MODEL: ${{ inputs.embedding_model }}" in workflow
    assert "EMBEDDING_DIMENSION: ${{ inputs.embedding_dimension }}" in workflow
    assert "--concurrency 1" in workflow
    assert "--budget-usd" in workflow
    assert "evals.generators.live_judge:judge_workflow_case" in workflow
    assert 'test "$LLM_MODEL" != "$EDUFLOW_EVAL_JUDGE_MODEL"' in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "docker compose down --volumes --remove-orphans" in workflow
