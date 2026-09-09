"""Provider-neutral resilience boundary for model and embedding calls."""

from __future__ import annotations

import asyncio
import random
import threading
import time
import weakref
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError

from config import get_settings

T = TypeVar("T")


class CircuitOpenError(RuntimeError):
    """Raised before I/O while a provider circuit is cooling down."""


@dataclass
class _CircuitState:
    failures: int = 0
    opened_at: float | None = None


_state_lock = threading.Lock()
_circuits: dict[str, _CircuitState] = {}
_semaphore_lock = threading.Lock()
_loop_semaphores: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


def _get_semaphore(limit: int) -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    with _semaphore_lock:
        current = _loop_semaphores.get(loop)
        if current is None or current[0] != limit:
            current = (limit, asyncio.Semaphore(limit))
            _loop_semaphores[loop] = current
        return current[1]


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, (TimeoutError, APIConnectionError, APITimeoutError, RateLimitError)):
        return True
    return isinstance(exc, APIStatusError) and exc.status_code >= 500


def _before_call(provider: str, reset_seconds: float) -> None:
    now = time.monotonic()
    with _state_lock:
        state = _circuits.setdefault(provider, _CircuitState())
        if state.opened_at is None:
            return
        if now - state.opened_at >= reset_seconds:
            state.opened_at = None
            state.failures = 0
            return
        raise CircuitOpenError("LLM provider circuit is temporarily open")


def _record_success(provider: str) -> None:
    with _state_lock:
        _circuits[provider] = _CircuitState()


def _record_failure(provider: str, threshold: int) -> None:
    with _state_lock:
        state = _circuits.setdefault(provider, _CircuitState())
        state.failures += 1
        if state.failures >= threshold:
            state.opened_at = time.monotonic()


async def execute_llm_call(
    provider: str,
    operation: str,
    call: Callable[[], Awaitable[T]],
) -> T:
    """Execute one logical call with bounded retries and provider circuit state."""
    from services.telemetry import ensure_llm_budget_available

    ensure_llm_budget_available()
    settings = get_settings()
    _before_call(provider, settings.llm_circuit_reset_seconds)
    semaphore = _get_semaphore(settings.llm_gateway_max_concurrency)
    max_attempts = settings.llm_gateway_max_retries + 1

    async with semaphore:
        for attempt in range(max_attempts):
            try:
                result = await asyncio.wait_for(
                    call(), timeout=settings.llm_timeout_seconds
                )
                _record_success(provider)
                return result
            except Exception as exc:
                retryable = _is_retryable(exc)
                final_attempt = attempt + 1 >= max_attempts
                if not retryable or final_attempt:
                    _record_failure(provider, settings.llm_circuit_failure_threshold)
                    raise

                from services.telemetry import record_gateway_retry

                record_gateway_retry(operation=operation, reason=type(exc).__name__)
                base = settings.llm_gateway_retry_base_seconds * (2**attempt)
                await asyncio.sleep(base + random.uniform(0, base * 0.2))


async def execute_llm_call_with_fallback(
    primary_provider: str,
    operation: str,
    primary_call: Callable[[], Awaitable[T]],
    *,
    fallback_provider: str | None = None,
    fallback_call: Callable[[], Awaitable[T]] | None = None,
) -> tuple[T, bool]:
    """Use backup only for exhausted transient failures or an open circuit."""
    try:
        return await execute_llm_call(primary_provider, operation, primary_call), False
    except Exception as exc:
        if (
            not fallback_provider
            or fallback_call is None
            or not (_is_retryable(exc) or isinstance(exc, CircuitOpenError))
        ):
            raise
        from services.telemetry import record_provider_fallback

        record_provider_fallback(operation=operation, reason=type(exc).__name__)
        result = await execute_llm_call(
            fallback_provider,
            f"{operation}.fallback",
            fallback_call,
        )
        return result, True


def reset_gateway_state() -> None:
    """Reset process state for deterministic tests."""
    with _state_lock:
        _circuits.clear()
