"""Request context and LLM metric aggregation tests."""

import asyncio

import pytest
from services.telemetry import (
    LLMBudgetExceededError,
    ensure_llm_budget_available,
    llm_budget_scope,
    record_http_request,
    record_llm_call,
    record_sse_connection_closed,
    record_sse_connection_started,
    reset_telemetry,
    telemetry_snapshot,
)


def test_llm_metrics_accumulate_without_prompt_content():
    reset_telemetry()
    record_llm_call(input_tokens=10, output_tokens=5, duration_ms=100)
    record_llm_call(
        input_tokens=20,
        output_tokens=10,
        duration_ms=300,
        model="provider/model",
        operation="structured",
        estimated_cost_usd=0.001,
    )
    snapshot = telemetry_snapshot()
    assert snapshot["counters"]["llm_calls_total"] == 2
    assert snapshot["counters"]["llm_input_tokens_total"] == 30
    assert snapshot["counters"]["llm_duration_ms_mean"] == 200
    assert snapshot["counters"]["llm_duration_ms_p95"] == 300
    assert snapshot["counters"]["llm_calls.model.provider_model"] == 1
    assert snapshot["counters"]["llm_calls.operation.structured"] == 1
    assert snapshot["counters"]["llm_estimated_cost_usd_total"] == 0.001
    assert "prompt" not in snapshot


def test_workflow_budget_blocks_calls_after_token_limit_is_crossed():
    reset_telemetry()
    with llm_budget_scope(max_tokens=10, max_cost_usd=1) as budget:
        record_llm_call(input_tokens=4, output_tokens=5, duration_ms=1)
        ensure_llm_budget_available()
        with pytest.raises(LLMBudgetExceededError):
            record_llm_call(input_tokens=2, output_tokens=0, duration_ms=1)
        with pytest.raises(LLMBudgetExceededError):
            ensure_llm_budget_available()

    assert budget.used_tokens == 11
    assert budget.input_tokens == 6
    assert budget.output_tokens == 5
    assert telemetry_snapshot()["counters"]["llm_budget_exceeded_total"] == 1


def test_workflow_budget_enforces_estimated_cost_limit():
    with llm_budget_scope(max_tokens=100, max_cost_usd=0.01):
        with pytest.raises(LLMBudgetExceededError):
            record_llm_call(
                input_tokens=1,
                output_tokens=1,
                duration_ms=1,
                estimated_cost_usd=0.02,
            )


@pytest.mark.asyncio
async def test_budget_scope_can_close_from_a_different_async_generator_task():
    """SSE cancellation must not fail ContextVar cleanup in aclose()."""
    async def stream():
        with llm_budget_scope(max_tokens=100, max_cost_usd=1):
            yield "chunk"

    generator = stream()
    assert await anext(generator) == "chunk"
    await asyncio.create_task(generator.aclose())


def test_http_and_sse_metrics_include_p95_error_rate_and_active_gauge():
    reset_telemetry()
    record_http_request(
        method="GET",
        route="/api/projects/{project_id}",
        status_code=200,
        duration_ms=10,
    )
    record_http_request(
        method="POST",
        route="/api/projects/{project_id}",
        status_code=503,
        duration_ms=50,
    )
    record_sse_connection_started()
    record_sse_connection_started()
    record_sse_connection_closed("done")

    counters = telemetry_snapshot()["counters"]
    assert counters["http_requests_total"] == 2
    assert counters["http_duration_ms_p95"] == 50
    assert counters["http_server_error_rate"] == 0.5
    assert counters["sse_connections_total"] == 2
    assert counters["sse_active_connections"] == 1
    assert counters["sse_connections_closed.done"] == 1
