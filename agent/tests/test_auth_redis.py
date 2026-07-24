"""Redis integration coverage for authentication rate-limit primitives."""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest
import pytest_asyncio
from redis.asyncio import Redis

from services.auth_rate_limit import (
    AuthRateLimited,
    _increment,
    _registration_key,
    check_registration_limit,
    clear_login_failures,
    login_attempt_lock,
    login_key,
    record_login_failure,
)


pytestmark = pytest.mark.redis


class _StartGate:
    """Release every worker together so the Lua increment contest is real."""

    def __init__(self, participants: int) -> None:
        self.participants = participants
        self.arrivals = 0
        self._released = asyncio.Event()

    async def wait(self) -> None:
        self.arrivals += 1
        if self.arrivals == self.participants:
            self._released.set()
        await asyncio.wait_for(self._released.wait(), timeout=5)


@pytest_asyncio.fixture
async def redis_client():
    """Use the real isolated CI Redis service, never a behavioral double."""
    client = Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379"), decode_responses=True)
    try:
        await client.ping()
        await client.flushdb()
        yield client
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_real_redis_counter_expiry_and_atomic_concurrency(redis_client: Redis) -> None:
    """Lua increments keep one expiry while concurrent callers cannot exceed the limit."""
    expiry_key = f"auth:test:expiry:{uuid.uuid4()}"
    count, ttl = await _increment(redis_client, expiry_key, 1)
    assert count == 1
    assert 1 <= ttl <= 1
    await asyncio.sleep(1.1)
    assert await redis_client.get(expiry_key) is None

    client_ip = "198.51.100.10"
    gate = _StartGate(20)

    async def increment() -> None:
        await gate.wait()
        await check_registration_limit(redis_client, client_ip)

    results = await asyncio.gather(
        *(increment() for _ in range(20)),
        return_exceptions=True,
    )
    assert gate.arrivals == 20
    assert sum(item is None for item in results) == 5
    assert sum(isinstance(item, AuthRateLimited) for item in results) == 15
    ttl = await redis_client.ttl(_registration_key(client_ip))
    assert 1 <= ttl <= 3600


@pytest.mark.asyncio
async def test_real_redis_login_lock_serializes_failure_and_success(redis_client: Redis) -> None:
    """The ownership-checked Redis lock keeps login outcome ordering intact."""
    client_ip = "198.51.100.11"
    email = "student@example.com"
    failure_entered = asyncio.Event()
    release_failure = asyncio.Event()
    order: list[str] = []

    async def failed_attempt() -> None:
        async with login_attempt_lock(redis_client, client_ip, email):
            order.append("failure")
            failure_entered.set()
            await release_failure.wait()
            await record_login_failure(redis_client, client_ip, email)

    async def successful_attempt() -> None:
        await failure_entered.wait()
        async with login_attempt_lock(redis_client, client_ip, email):
            order.append("success")
            await clear_login_failures(redis_client, client_ip, email)

    failure = asyncio.create_task(failed_attempt())
    await failure_entered.wait()
    success = asyncio.create_task(successful_attempt())
    await asyncio.sleep(0)
    assert order == ["failure"]
    release_failure.set()
    await asyncio.gather(failure, success)

    assert order == ["failure", "success"]
    assert await redis_client.get(login_key(client_ip, email)) is None
