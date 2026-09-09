"""Redis-first fixed-window limiter with a bounded process-local fallback."""

from __future__ import annotations

import asyncio
import hashlib
import time

_fallback: dict[str, tuple[int, float]] = {}
_fallback_lock = asyncio.Lock()
_MAX_FALLBACK_KEYS = 10_000


def _key(scope: str, identifier: str) -> str:
    digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
    return f"eduflow:rate:{scope}:{digest}"


async def check_rate_limit(
    scope: str, identifier: str, *, limit: int, window_seconds: int
) -> int | None:
    """Return retry-after seconds when blocked, otherwise ``None``."""
    key = _key(scope, identifier)
    try:
        from api.export import _get_redis

        client = await _get_redis()
        if client is not None:
            count, ttl = await asyncio.to_thread(
                _increment_redis_window, client, key, window_seconds
            )
            return max(1, ttl) if count > limit else None
    except Exception:
        pass
    return await _check_process_window(key, limit, window_seconds)


def _increment_redis_window(client, key: str, window_seconds: int) -> tuple[int, int]:
    pipe = client.pipeline(transaction=True)
    pipe.incr(key)
    pipe.expire(key, window_seconds, nx=True)
    pipe.ttl(key)
    count, _, ttl = pipe.execute()
    return int(count), int(ttl if ttl and ttl > 0 else window_seconds)


async def _check_process_window(key: str, limit: int, window_seconds: int) -> int | None:
    now = time.monotonic()
    async with _fallback_lock:
        count, expires = _fallback.get(key, (0, now + window_seconds))
        if now >= expires:
            count, expires = 0, now + window_seconds
        count += 1
        _fallback[key] = (count, expires)
        if len(_fallback) > _MAX_FALLBACK_KEYS:
            expired = [item for item, (_, end) in _fallback.items() if end <= now]
            for item in expired:
                _fallback.pop(item, None)
            while len(_fallback) > _MAX_FALLBACK_KEYS:
                _fallback.pop(next(iter(_fallback)))
        return max(1, int(expires - now)) if count > limit else None
