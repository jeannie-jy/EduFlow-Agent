"""Run core EduFlowBench cases through the production LangGraph workflow."""

from __future__ import annotations

import time
import uuid
from typing import Any

from evals.models import EvalCase

EVAL_NAMESPACE = uuid.UUID("ee000000-0000-4000-8000-000000000050")


async def generate_workflow_case(case: EvalCase) -> dict[str, Any]:
    """Generate one teaching artifact without API persistence or HITL pauses."""
    from services.generate_service import run_generation_sync_with_usage

    started = time.perf_counter()
    project_id = str(uuid.uuid5(EVAL_NAMESPACE, case.case_id))
    thread_id = f"eval:{case.case_id}:{uuid.uuid4().hex}"
    state, usage = await run_generation_sync_with_usage(
        project_id,
        case.topic,
        constraints={
            **case.constraints,
            "difficulty": case.difficulty,
            "eval_case_id": case.case_id,
            # Keep benchmark expectations visible to the production Coder so
            # required concepts are explicitly taught, not merely inferred by
            # the offline grader after generation.
            "required_concepts": case.expected.required_concepts,
            "forbidden_claims": case.expected.forbidden_claims,
            # Evaluation-only structural expectations. Normal user requests do
            # not carry these keys and retain their existing planning policy.
            "min_frames": case.expected.min_frames,
            "max_frames": case.expected.max_frames,
            # Keep online Coder responses below common provider completion
            # ceilings; production requests retain the richer output profile.
            "eval_output_profile": "compact",
            "eval_max_frames": min(case.expected.max_frames, 8),
            # Freeze decoding for comparable online runs. Production requests
            # do not set this flag and keep their node-specific temperatures.
            "eval_deterministic": True,
        },
        materials=case.materials,
        thread_id=thread_id,
    )
    artifact = state.get("dsl")
    if not isinstance(artifact, dict):
        raise TypeError("production workflow returned no DSL artifact")
    # The production graph intentionally has deterministic fallbacks for user
    # experience.  An online benchmark must not count those fallbacks as a
    # successful model run when the provider is unavailable (for example HTTP
    # 402 insufficient balance).  Valid no-evidence cases still use the LLM in
    # Planner/Knowledge/Quality, so their usage is non-zero.
    input_tokens = int(usage.get("input", 0))
    output_tokens = int(usage.get("output", 0))
    if input_tokens + output_tokens <= 0:
        raise RuntimeError(
            "online benchmark produced no candidate LLM tokens; "
            "provider failure was hidden by deterministic fallback"
        )
    retrieval = state.get("retrieval") or {}
    knowledge_graph = state.get("knowledge_graph") or {}
    return {
        "artifact": artifact,
        "usage": {
            "input": input_tokens,
            "output": output_tokens,
        },
        "cost_usd": float(usage.get("cost_usd", 0.0)),
        "metadata": {
            "raw_coder_output": state.get("raw_coder_output") or {},
            "normalization_report": artifact.get("normalization_report") or {},
            "quality_report": state.get("quality_report") or {},
            "algorithm_trace_compilation": artifact.get("algorithm_trace_compilation") or {},
            "candidate_latency_ms": round((time.perf_counter() - started) * 1000, 2),
            # Keep evidence provenance outside the artifact file as auditable
            # runner metadata while the DSL itself still carries the bounded
            # knowledge_graph.sources field.
            "retrieval": retrieval,
            "knowledge_source_ids": [
                str(source.get("source_id"))
                for source in knowledge_graph.get("sources", [])
                if isinstance(source, dict) and source.get("source_id")
            ],
            "artifact_source_ids": [
                str(source.get("source_id"))
                for source in (artifact.get("knowledge_graph") or {}).get("sources", [])
                if isinstance(source, dict) and source.get("source_id")
            ],
        },
    }
