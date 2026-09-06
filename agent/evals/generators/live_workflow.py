"""Run core EduFlowBench cases through the production LangGraph workflow."""

from __future__ import annotations

import uuid
from typing import Any

from evals.models import EvalCase

EVAL_NAMESPACE = uuid.UUID("ee000000-0000-4000-8000-000000000050")


async def generate_workflow_case(case: EvalCase) -> dict[str, Any]:
    """Generate one teaching artifact without API persistence or HITL pauses."""
    from services.generate_service import run_generation_sync_with_usage

    project_id = str(uuid.uuid5(EVAL_NAMESPACE, case.case_id))
    thread_id = f"eval:{case.case_id}:{uuid.uuid4().hex}"
    state, usage = await run_generation_sync_with_usage(
        project_id,
        case.topic,
        constraints={
            **case.constraints,
            "difficulty": case.difficulty,
            "eval_case_id": case.case_id,
        },
        materials=case.materials,
        thread_id=thread_id,
    )
    artifact = state.get("dsl")
    if not isinstance(artifact, dict):
        raise TypeError("production workflow returned no DSL artifact")
    return {
        "artifact": artifact,
        "usage": {
            "input": int(usage.get("input", 0)),
            "output": int(usage.get("output", 0)),
        },
        "cost_usd": float(usage.get("cost_usd", 0.0)),
        "metadata": {"quality_report": state.get("quality_report") or {}},
    }
