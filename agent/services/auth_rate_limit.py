"""Redis-backed, fixed-window limits for authentication endpoints."""

from __future__ import annotations

import asyncio
import hashlib
import secrets
from contextlib import asynccontextmanager

from redis.exceptions import RedisError


LOGIN_FAILURE_LIMIT = 5
LOGIN_FAILURE_WINDOW_SECONDS = 15 * 60
REGISTRATION_LIMIT = 5
REGISTRATION_WINDOW_SECONDS = 60 * 60
REFRESH_LIMIT = 30
REFRESH_WINDOW_SECONDS = 60
LOGIN_LOCK_TTL_SECONDS = 30
LOGIN_LOCK_WAIT_SECONDS = 5

_INCREMENT_WITH_EXPIRY = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
return {count, ttl}
"""

_UNLOCK_IF_OWNER = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""


class AuthRateLimited(Exception):
    """Raised when an authentication fixed window has been exhausted."""

    def __init__(self, retry_after: int) -> None:
        self.retry_after = max(1, retry_after)
        super().__init__("authentication rate limit exceeded")


class AuthRateLimitUnavailable(Exception):
    """Raised when Redis cannot safely enforce an authentication limit."""


def _digest(value: str) -> str:
    """Return a short opaque identifier suitable for a Redis key."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def login_key(client_ip: str, email: str) -> str:
    """Return the privacy-preserving failed-login counter key."""
    return f"auth:login:{_digest(client_ip)}:{_digest(email)}"


def _login_lock_key(client_ip: str, email: str) -> str:
    return f"{login_key(client_ip, email)}:lock"


def _registration_key(client_ip: str) -> str:
    return f"auth:register:{_digest(client_ip)}"


def _refresh_key(session_key: str) -> str:
    return f"auth:refresh:{_digest(session_key)}"


async def _increment(redis, key: str, window_seconds: int) -> tuple[int, int]:
    """Atomically increment a counter and set its expiry on first use."""
    try:
        count, retry_after = await redis.eval(
            _INCREMENT_WITH_EXPIRY,
            1,
            key,
            window_seconds,
        )
    except RedisError as error:
        raise AuthRateLimitUnavailable from error
    return int(count), max(1, int(retry_after))


async def _check_and_increment(redis, key: str, limit: int, window_seconds: int) -> None:
    count, retry_after = await _increment(redis, key, window_seconds)
    if count > limit:
        raise AuthRateLimited(retry_after)


async def _check_existing(redis, key: str, limit: int) -> None:
    """Check a login-failure counter without charging a successful login."""
    try:
        count = await redis.get(key)
        if count is not None and int(count) >= limit:
            retry_after = await redis.ttl(key)
            raise AuthRateLimited(int(retry_after))
    except AuthRateLimited:
        raise
    except RedisError as error:
        raise AuthRateLimitUnavailable from error


async def check_login_limit(redis, client_ip: str, normalized_email: str) -> None:
    """Reject a sixth failed-login attempt in a 15-minute window."""
    await _check_existing(
        redis,
        login_key(client_ip, normalized_email),
        LOGIN_FAILURE_LIMIT,
    )


async def _release_login_lock(redis, key: str, token: str) -> None:
    """Delete a lock only when it is still owned by this request."""
    try:
        await redis.eval(_UNLOCK_IF_OWNER, 1, key, token)
    except RedisError as error:
        raise AuthRateLimitUnavailable from error


@asynccontextmanager
async def login_attempt_lock(redis, client_ip: str, normalized_email: str):
    """Serialize one login bucket through checking, verification, and outcome."""
    key = _login_lock_key(client_ip, normalized_email)
    token = secrets.token_urlsafe(24)
    deadline = asyncio.get_running_loop().time() + LOGIN_LOCK_WAIT_SECONDS

    while True:
        try:
            acquired = await redis.set(
                key,
                token,
                nx=True,
                ex=LOGIN_LOCK_TTL_SECONDS,
            )
        except RedisError as error:
            raise AuthRateLimitUnavailable from error
        if acquired:
            break
        if asyncio.get_running_loop().time() >= deadline:
            raise AuthRateLimited(1)
        await asyncio.sleep(0.01)

    try:
        yield
    finally:
        await _release_login_lock(redis, key, token)


async def record_login_failure(redis, client_ip: str, normalized_email: str) -> None:
    """Record a failed login without pre-consuming a successful attempt."""
    key = login_key(client_ip, normalized_email)
    try:
        await redis.eval(
            _INCREMENT_WITH_EXPIRY,
            1,
            key,
            LOGIN_FAILURE_WINDOW_SECONDS,
        )
    except RedisError as error:
        raise AuthRateLimitUnavailable from error


async def clear_login_failures(redis, client_ip: str, normalized_email: str) -> None:
    """Clear the failed-login window following a successful authentication."""
    try:
        await redis.delete(login_key(client_ip, normalized_email))
    except RedisError as error:
        raise AuthRateLimitUnavailable from error


async def check_registration_limit(redis, client_ip: str) -> None:
    """Reject a sixth registration from one IP in an hour."""
    await _check_and_increment(
        redis,
        _registration_key(client_ip),
        REGISTRATION_LIMIT,
        REGISTRATION_WINDOW_SECONDS,
    )


async def check_refresh_limit(redis, session_key: str) -> None:
    """Reject a 31st refresh attempt for one session key in a minute."""
    await _check_and_increment(
        redis,
        _refresh_key(session_key),
        REFRESH_LIMIT,
        REFRESH_WINDOW_SECONDS,
    )
