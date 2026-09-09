"""Lightweight process telemetry with request-context propagation.

The JSON snapshot is dependency-free and useful locally; production deployments
can export the same events to OpenTelemetry without changing call sites.
"""

from __future__ import annotations

import contextvars
import math
import re
import threading
from collections import defaultdict, deque
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="background")
_lock = threading.Lock()
_counters: dict[str, float] = defaultdict(float)
_llm_durations: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=1000))
_http_durations: deque[float] = deque(maxlen=2000)


class LLMBudgetExceededError(RuntimeError):
    """A workflow consumed its configured request-level LLM budget."""


@dataclass
class LLMBudgetState:
    max_tokens: int
    max_cost_usd: float
    used_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    used_cost_usd: float = 0.0
    exceeded: bool = False


_llm_budget_var: contextvars.ContextVar[LLMBudgetState | None] = contextvars.ContextVar(
    "llm_budget", default=None
)


def _metric_label(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", value)[:80] or "unknown"


def record_llm_call(
    *,
    input_tokens: int,
    output_tokens: int,
    duration_ms: float,
    model: str = "unknown",
    operation: str = "unknown",
    estimated_cost_usd: float = 0.0,
    endpoint: str | None = None,
    prompt_version: str | None = None,
) -> None:
    with _lock:
        _counters["llm_calls_total"] += 1
        _counters["llm_input_tokens_total"] += input_tokens
        _counters["llm_output_tokens_total"] += output_tokens
        _counters["llm_duration_ms_total"] += duration_ms
        _counters["llm_estimated_cost_usd_total"] += estimated_cost_usd
        _counters[f"llm_calls.model.{_metric_label(model)}"] += 1
        _counters[f"llm_calls.operation.{_metric_label(operation)}"] += 1
        _llm_durations[_metric_label(model)].append(duration_ms)
    from services.workflow_trace import record_trace_llm_call

    record_trace_llm_call(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=estimated_cost_usd,
        model=model,
        endpoint=endpoint,
        prompt_version=prompt_version,
    )
    charge_llm_budget(
        input_tokens + output_tokens,
        estimated_cost_usd,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


@contextmanager
def llm_budget_scope(max_tokens: int, max_cost_usd: float) -> Iterator[LLMBudgetState]:
    """Create one budget shared by all calls and child tasks in a workflow run."""
    state = LLMBudgetState(max_tokens=max_tokens, max_cost_usd=max_cost_usd)
    previous = _llm_budget_var.get()
    _llm_budget_var.set(state)
    try:
        yield state
    finally:
        # SSE libraries may finalize an async generator in a cancellation task
        # different from the one that entered this scope. ContextVar tokens are
        # context-bound, so reset(token) raises ValueError in that case.
        _llm_budget_var.set(previous)


def ensure_llm_budget_available() -> None:
    state = _llm_budget_var.get()
    if state is not None and state.exceeded:
        raise LLMBudgetExceededError("LLM request budget has been exhausted")


def charge_llm_budget(
    tokens: int,
    cost_usd: float,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> None:
    state = _llm_budget_var.get()
    if state is None:
        return
    state.used_tokens += max(tokens, 0)
    state.input_tokens += max(input_tokens, 0)
    state.output_tokens += max(output_tokens, 0)
    state.used_cost_usd += max(cost_usd, 0.0)
    if (
        state.used_tokens > state.max_tokens
        or state.used_cost_usd > state.max_cost_usd
    ):
        state.exceeded = True
        with _lock:
            _counters["llm_budget_exceeded_total"] += 1
        raise LLMBudgetExceededError("LLM request budget has been exhausted")


def record_gateway_retry(*, operation: str, reason: str) -> None:
    """Count bounded retry attempts without recording prompt or response content."""
    with _lock:
        _counters["llm_retries_total"] += 1
        _counters[f"llm_retries.{operation}"] += 1
        _counters[f"llm_retry_reason.{reason}"] += 1
    from services.workflow_trace import record_trace_retry

    record_trace_retry()


def record_provider_fallback(*, operation: str, reason: str) -> None:
    with _lock:
        _counters["llm_provider_fallbacks_total"] += 1
        _counters[f"llm_provider_fallbacks.{_metric_label(operation)}"] += 1
        _counters[f"llm_provider_fallback_reason.{_metric_label(reason)}"] += 1


def record_http_request(*, method: str, route: str, status_code: int, duration_ms: float) -> None:
    """Record bounded-cardinality API metrics using the route template, not raw URLs."""
    method_label = _metric_label(method.upper())
    route_label = _metric_label(route)
    status_class = f"{max(status_code, 0) // 100}xx"
    with _lock:
        _counters["http_requests_total"] += 1
        _counters[f"http_requests.method.{method_label}"] += 1
        _counters[f"http_requests.route.{route_label}"] += 1
        _counters[f"http_responses.status.{status_class}"] += 1
        if status_code >= 500:
            _counters["http_server_errors_total"] += 1
        _http_durations.append(max(duration_ms, 0))


def record_sse_connection_started() -> None:
    with _lock:
        _counters["sse_connections_total"] += 1
        _counters["sse_active_connections"] += 1


def record_sse_connection_closed(outcome: str) -> None:
    with _lock:
        _counters["sse_active_connections"] = max(
            _counters["sse_active_connections"] - 1, 0
        )
        _counters[f"sse_connections_closed.{_metric_label(outcome)}"] += 1


def telemetry_snapshot() -> dict[str, Any]:
    with _lock:
        counters = dict(_counters)
        durations = {
            model: list(samples) for model, samples in _llm_durations.items()
        }
        http_durations = list(_http_durations)
    calls = counters.get("llm_calls_total", 0)
    counters["llm_duration_ms_mean"] = (
        round(counters.get("llm_duration_ms_total", 0) / calls, 2) if calls else 0
    )
    all_samples = [sample for values in durations.values() for sample in values]
    counters["llm_duration_ms_p95"] = _percentile_95(all_samples)
    counters["http_duration_ms_p95"] = _percentile_95(http_durations)
    http_total = counters.get("http_requests_total", 0)
    counters["http_server_error_rate"] = (
        round(counters.get("http_server_errors_total", 0) / http_total, 6)
        if http_total else 0
    )
    for model, samples in durations.items():
        counters[f"llm_duration_ms_p95.model.{model}"] = _percentile_95(samples)
    return {"scope": "process", "counters": counters}


def _percentile_95(samples: list[float]) -> float:
    if not samples:
        return 0
    ordered = sorted(samples)
    index = max(0, math.ceil(len(ordered) * 0.95) - 1)
    return round(ordered[index], 2)


def reset_telemetry() -> None:
    """Test-only reset; process startup naturally begins with empty counters."""
    with _lock:
        _counters.clear()
        _llm_durations.clear()
        _http_durations.clear()
