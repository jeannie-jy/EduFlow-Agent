"""Deterministic tests for the provider-neutral LLM resilience boundary."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from services.llm_gateway import (
    CircuitOpenError,
    execute_llm_call,
    execute_llm_call_with_fallback,
    reset_gateway_state,
)
from services.telemetry import reset_telemetry, telemetry_snapshot
from services.telemetry import LLMBudgetExceededError, charge_llm_budget, llm_budget_scope


def _settings(**overrides):
    values = {
        "llm_circuit_reset_seconds": 30,
        "llm_gateway_max_concurrency": 2,
        "llm_gateway_max_retries": 2,
        "llm_timeout_seconds": 1,
        "llm_circuit_failure_threshold": 5,
        "llm_gateway_retry_base_seconds": 0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.fixture(autouse=True)
def _reset_gateway():
    reset_gateway_state()
    reset_telemetry()
    yield
    reset_gateway_state()


@pytest.mark.asyncio
async def test_retryable_timeout_is_retried_and_counted():
    call = AsyncMock(side_effect=[TimeoutError("provider timeout"), "ok"])
    with patch("services.llm_gateway.get_settings", return_value=_settings()):
        result = await execute_llm_call("provider-a", "chat", call)

    assert result == "ok"
    assert call.await_count == 2
    counters = telemetry_snapshot()["counters"]
    assert counters["llm_retries_total"] == 1
    assert counters["llm_retry_reason.TimeoutError"] == 1


@pytest.mark.asyncio
async def test_non_retryable_error_fails_once():
    call = AsyncMock(side_effect=ValueError("bad request"))
    with patch("services.llm_gateway.get_settings", return_value=_settings()):
        with pytest.raises(ValueError, match="bad request"):
            await execute_llm_call("provider-a", "chat", call)

    assert call.await_count == 1


@pytest.mark.asyncio
async def test_circuit_opens_after_failure_threshold():
    call = AsyncMock(side_effect=TimeoutError("down"))
    settings = _settings(
        llm_gateway_max_retries=0,
        llm_circuit_failure_threshold=1,
    )
    with patch("services.llm_gateway.get_settings", return_value=settings):
        with pytest.raises(TimeoutError):
            await execute_llm_call("provider-a", "chat", call)
        with pytest.raises(CircuitOpenError):
            await execute_llm_call("provider-a", "chat", call)

    assert call.await_count == 1


@pytest.mark.asyncio
async def test_concurrency_limit_bounds_in_flight_calls():
    active = 0
    maximum = 0

    async def tracked_call():
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0.01)
        active -= 1
        return "ok"

    with patch("services.llm_gateway.get_settings", return_value=_settings()):
        results = await asyncio.gather(
            *(execute_llm_call("provider-a", "chat", tracked_call) for _ in range(6))
        )

    assert results == ["ok"] * 6
    assert maximum == 2


@pytest.mark.asyncio
async def test_exhausted_request_budget_rejects_before_provider_io():
    call = AsyncMock(return_value="must-not-run")
    with llm_budget_scope(max_tokens=1, max_cost_usd=1):
        with pytest.raises(LLMBudgetExceededError):
            charge_llm_budget(2, 0)
        with pytest.raises(LLMBudgetExceededError):
            await execute_llm_call("provider-a", "chat", call)

    call.assert_not_awaited()


@pytest.mark.asyncio
async def test_transient_primary_failure_uses_configured_backup():
    primary = AsyncMock(side_effect=TimeoutError("primary unavailable"))
    backup = AsyncMock(return_value="backup-result")
    settings = _settings(llm_gateway_max_retries=0)
    with patch("services.llm_gateway.get_settings", return_value=settings):
        result, used_fallback = await execute_llm_call_with_fallback(
            "primary",
            "structured",
            primary,
            fallback_provider="backup",
            fallback_call=backup,
        )

    assert result == "backup-result"
    assert used_fallback is True
    primary.assert_awaited_once()
    backup.assert_awaited_once()
    assert telemetry_snapshot()["counters"]["llm_provider_fallbacks_total"] == 1


@pytest.mark.asyncio
async def test_non_transient_primary_failure_does_not_use_backup():
    primary = AsyncMock(side_effect=ValueError("invalid request"))
    backup = AsyncMock(return_value="must-not-run")
    with patch("services.llm_gateway.get_settings", return_value=_settings()):
        with pytest.raises(ValueError):
            await execute_llm_call_with_fallback(
                "primary",
                "chat",
                primary,
                fallback_provider="backup",
                fallback_call=backup,
            )

    backup.assert_not_awaited()
