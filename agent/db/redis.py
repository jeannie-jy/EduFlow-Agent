"""Shared asynchronous Redis client lifecycle."""

from __future__ import annotations

from redis.asyncio import Redis

from config import get_settings


_redis: Redis | None = None


def get_redis() -> Redis:
    """Return the process-wide Redis client, creating it lazily."""
    global _redis
    if _redis is None:
        _redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    return _redis


async def close_redis() -> None:
    """Close and discard the process-wide Redis client."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
