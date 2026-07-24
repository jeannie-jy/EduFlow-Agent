from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import select

from api.auth_errors import (
    access_token_invalid,
    account_disabled,
    auth_rate_limited,
    email_registered,
    invalid_credentials,
    password_policy_violation,
    refresh_token_invalid,
)
from api.error_handlers import register_error_handlers
from schema.auth import AuthResponse, LoginRequest, RegisterRequest, UserResponse


class FakeRedis:
    """Small async Redis double for fixed-window rate-limit tests."""

    def __init__(self) -> None:
        self.values: dict[str, int] = {}
        self.expires_in: dict[str, int] = {}

    async def eval(self, _script: str, _numkeys: int, key: str, window: int):
        count = self.values.get(key, 0) + 1
        self.values[key] = count
        self.expires_in.setdefault(key, int(window))
        return [count, self.expires_in[key]]

    async def get(self, key: str) -> int | None:
        return self.values.get(key)

    async def ttl(self, key: str) -> int:
        return self.expires_in.get(key, -2)

    async def delete(self, key: str) -> int:
        existed = key in self.values
        self.values.pop(key, None)
        self.expires_in.pop(key, None)
        return int(existed)


class UnavailableRedis:
    """Redis double that models a connection outage."""

    async def eval(self, *_args, **_kwargs):
        raise RedisConnectionError("Redis is unavailable")


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> FakeRedis:
    """Keep HTTP auth tests isolated from a real Redis service."""
    redis = FakeRedis()
    monkeypatch.setattr("api.auth.get_redis", lambda: redis, raising=False)
    return redis


async def _register(
    client,
    *,
    email: str = "student@example.com",
    headers: dict[str, str] | None = None,
):
    response = await client.post(
        "/api/auth/register",
        json={
            "email": email,
            "nickname": "Student",
            "password": "learning2026",
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response


def _assert_cookie_cleared(response) -> None:
    cookie = response.headers["set-cookie"].lower()
    assert "eduflow_refresh=" in cookie
    assert "max-age=0" in cookie
    assert "path=/api/auth" in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie


@pytest.mark.asyncio
async def test_register_sets_refresh_cookie_and_omits_sensitive_values(auth_api_client) -> None:
    response = await _register(auth_api_client.client)

    assert "eduflow_refresh=" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]
    assert "Path=/api/auth" in response.headers["set-cookie"]
    assert "Max-Age=2592000" in response.headers["set-cookie"]
    assert "Secure" in response.headers["set-cookie"]
    assert "Domain=" not in response.headers["set-cookie"]
    assert response.json()["user"]["email"] == "student@example.com"
    assert "password" not in response.text.lower()
    assert "refresh_token" not in response.text


@pytest.mark.asyncio
async def test_registration_truncates_oversized_user_agent(auth_api_client) -> None:
    from db.models import AuthSession

    oversized_user_agent = "browser/" + "x" * 600
    await _register(
        auth_api_client.client,
        headers={"User-Agent": oversized_user_agent},
    )

    async with auth_api_client.session_factory() as session:
        auth_session = await session.scalar(select(AuthSession))
    assert auth_session is not None
    assert auth_session.user_agent == oversized_user_agent[:500]


@pytest.mark.asyncio
async def test_register_commits_user_record(auth_api_client) -> None:
    from db.models import User

    await _register(auth_api_client.client)

    async with auth_api_client.session_factory() as session:
        user = await session.scalar(
            select(User).where(User.email_normalized == "student@example.com")
        )
    assert user is not None


@pytest.mark.asyncio
async def test_register_rolls_back_on_unhandled_service_error(
    auth_api_client, monkeypatch: pytest.MonkeyPatch
) -> None:
    from db.models import User

    async def create_then_fail(session, request, user_agent):
        session.add(
            User(
                id=uuid4(),
                email="rollback@example.com",
                email_normalized="rollback@example.com",
                nickname="Rollback",
                password_hash="not-a-real-password-hash",
            )
        )
        raise RuntimeError("simulated persistence failure")

    monkeypatch.setattr("api.auth.register_user", create_then_fail)
    response = await auth_api_client.client.post(
        "/api/auth/register",
        json={
            "email": "rollback@example.com",
            "nickname": "Rollback",
            "password": "learning2026",
        },
    )

    assert response.status_code == 500
    async with auth_api_client.session_factory() as session:
        user = await session.scalar(
            select(User).where(User.email_normalized == "rollback@example.com")
        )
    assert user is None


@pytest.mark.asyncio
async def test_login_sets_refresh_cookie_and_preserves_invalid_credentials_privacy(
    auth_api_client,
) -> None:
    client = auth_api_client.client
    await _register(client)

    response = await client.post(
        "/api/auth/login",
        json={"email": "student@example.com", "password": "learning2026"},
    )
    assert response.status_code == 200
    assert "eduflow_refresh=" in response.headers["set-cookie"]

    invalid = await client.post(
        "/api/auth/login",
        json={"email": "missing@example.com", "password": "learning2026"},
    )
    assert invalid.status_code == 401
    assert invalid.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert invalid.headers["www-authenticate"] == "Bearer"


@pytest.mark.asyncio
async def test_refresh_rotates_cookie_and_replay_invalidates_session_family(auth_api_client) -> None:
    client = auth_api_client.client
    await _register(client)
    original_refresh = client.cookies.get("eduflow_refresh")
    assert original_refresh

    refreshed = await client.post("/api/auth/refresh")
    assert refreshed.status_code == 200
    rotated_refresh = client.cookies.get("eduflow_refresh")
    assert rotated_refresh and rotated_refresh != original_refresh
    assert original_refresh not in refreshed.text
    assert rotated_refresh not in refreshed.text

    client.cookies.clear()
    replay = await client.post(
        "/api/auth/refresh",
        headers={"Cookie": f"eduflow_refresh={original_refresh}"},
    )
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "REFRESH_TOKEN_INVALID"
    assert replay.headers["www-authenticate"] == "Bearer"
    _assert_cookie_cleared(replay)

    replacement = await client.post(
        "/api/auth/refresh",
        headers={"Cookie": f"eduflow_refresh={rotated_refresh}"},
    )
    assert replacement.status_code == 401
    assert replacement.json()["error"]["code"] == "REFRESH_TOKEN_INVALID"


@pytest.mark.asyncio
async def test_invalid_refresh_clears_cookie(auth_api_client) -> None:
    response = await auth_api_client.client.post(
        "/api/auth/refresh",
        headers={"Cookie": "eduflow_refresh=not-a-valid-token"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "REFRESH_TOKEN_INVALID"
    assert response.headers["www-authenticate"] == "Bearer"
    _assert_cookie_cleared(response)


@pytest.mark.asyncio
async def test_logout_is_idempotent_revokes_refresh_session_and_clears_cookie(auth_api_client) -> None:
    client = auth_api_client.client
    await _register(client)
    refresh_token = client.cookies.get("eduflow_refresh")
    assert refresh_token

    first_logout = await client.post("/api/auth/logout")
    assert first_logout.status_code == 204
    _assert_cookie_cleared(first_logout)

    second_logout = await client.post("/api/auth/logout")
    assert second_logout.status_code == 204
    _assert_cookie_cleared(second_logout)

    revoked = await client.post(
        "/api/auth/refresh",
        headers={"Cookie": f"eduflow_refresh={refresh_token}"},
    )
    assert revoked.status_code == 401
    assert revoked.json()["error"]["code"] == "REFRESH_TOKEN_INVALID"


@pytest.mark.asyncio
async def test_logout_all_revokes_every_session_and_clears_current_cookie(auth_api_client) -> None:
    client = auth_api_client.client
    registration = await _register(client)
    first_refresh = client.cookies.get("eduflow_refresh")
    login = await client.post(
        "/api/auth/login",
        json={"email": "student@example.com", "password": "learning2026"},
    )
    assert login.status_code == 200
    second_refresh = client.cookies.get("eduflow_refresh")
    assert first_refresh and second_refresh and first_refresh != second_refresh

    response = await client.post(
        "/api/auth/logout-all",
        headers={"Authorization": f"Bearer {registration.json()['access_token']}"},
    )
    assert response.status_code == 204
    _assert_cookie_cleared(response)

    revoked = await client.post(
        "/api/auth/refresh",
        headers={"Cookie": f"eduflow_refresh={second_refresh}"},
    )
    assert revoked.status_code == 401
    assert revoked.json()["error"]["code"] == "REFRESH_TOKEN_INVALID"


@pytest.mark.asyncio
async def test_me_requires_bearer_token(auth_api_client) -> None:
    response = await auth_api_client.client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "ACCESS_TOKEN_INVALID"
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.asyncio
async def test_me_returns_authenticated_user_without_sensitive_values(auth_api_client) -> None:
    client = auth_api_client.client
    registration = await _register(client)

    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {registration.json()['access_token']}"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "student@example.com"
    assert "password" not in response.text.lower()
    assert "refresh_token" not in response.text


@pytest.mark.asyncio
async def test_me_rejects_disabled_user_and_refresh_keeps_account_state_private(
    auth_api_client,
) -> None:
    from db.models import User

    client = auth_api_client.client
    registration = await _register(client)
    refresh_token = client.cookies.get("eduflow_refresh")
    assert refresh_token
    async with auth_api_client.session_factory() as session:
        user = await session.scalar(
            select(User).where(User.email_normalized == "student@example.com")
        )
        assert user is not None
        user.is_active = False
        await session.commit()

    me = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {registration.json()['access_token']}"},
    )
    assert me.status_code == 403
    assert me.json()["error"]["code"] == "ACCOUNT_DISABLED"

    refresh = await client.post(
        "/api/auth/refresh",
        headers={"Cookie": f"eduflow_refresh={refresh_token}"},
    )
    assert refresh.status_code == 401
    assert refresh.json()["error"]["code"] == "REFRESH_TOKEN_INVALID"
    _assert_cookie_cleared(refresh)


@pytest.mark.asyncio
async def test_refresh_rejects_untrusted_origin(auth_api_client) -> None:
    response = await auth_api_client.client.post(
        "/api/auth/refresh",
        headers={"Origin": "https://attacker.example"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_trusted_origin_preflight_allows_credentials(auth_api_client) -> None:
    response = await auth_api_client.client.options(
        "/api/auth/refresh",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["access-control-allow-credentials"] == "true"


@pytest.mark.asyncio
async def test_logout_rejects_untrusted_origin(auth_api_client) -> None:
    response = await auth_api_client.client.post(
        "/api/auth/logout",
        headers={"Origin": "https://attacker.example"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_sixth_failed_login_is_limited_with_retry_after(fake_redis: FakeRedis) -> None:
    from services.auth_rate_limit import (
        AuthRateLimited,
        check_login_limit,
        record_login_failure,
    )

    for _ in range(5):
        await check_login_limit(fake_redis, "198.51.100.10", "student@example.com")
        await record_login_failure(fake_redis, "198.51.100.10", "student@example.com")

    with pytest.raises(AuthRateLimited) as error:
        await check_login_limit(fake_redis, "198.51.100.10", "student@example.com")

    assert error.value.retry_after == 900


@pytest.mark.asyncio
async def test_successful_login_clears_its_failure_counter(fake_redis: FakeRedis) -> None:
    from services.auth_rate_limit import (
        clear_login_failures,
        login_key,
        record_login_failure,
    )

    client_ip = "198.51.100.10"
    email = "student@example.com"
    await record_login_failure(fake_redis, client_ip, email)
    await clear_login_failures(fake_redis, client_ip, email)

    assert login_key(client_ip, email) not in fake_redis.values


@pytest.mark.asyncio
async def test_sixth_registration_in_an_hour_is_limited(fake_redis: FakeRedis) -> None:
    from services.auth_rate_limit import AuthRateLimited, check_registration_limit

    for _ in range(5):
        await check_registration_limit(fake_redis, "198.51.100.10")

    with pytest.raises(AuthRateLimited) as error:
        await check_registration_limit(fake_redis, "198.51.100.10")

    assert error.value.retry_after == 3600


@pytest.mark.asyncio
async def test_thirty_first_refresh_in_a_minute_is_limited(fake_redis: FakeRedis) -> None:
    from services.auth_rate_limit import AuthRateLimited, check_refresh_limit

    for _ in range(30):
        await check_refresh_limit(fake_redis, "refresh-session-key")

    with pytest.raises(AuthRateLimited) as error:
        await check_refresh_limit(fake_redis, "refresh-session-key")

    assert error.value.retry_after == 60


@pytest.mark.asyncio
async def test_rate_limit_keys_do_not_expose_normalized_email(fake_redis: FakeRedis) -> None:
    from services.auth_rate_limit import login_key, record_login_failure

    normalized_email = "student@example.com"
    await record_login_failure(fake_redis, "198.51.100.10", normalized_email)
    key = login_key("198.51.100.10", normalized_email)

    assert normalized_email not in key
    assert key in fake_redis.values


@pytest.mark.asyncio
async def test_login_route_limits_before_a_sixth_credential_check(
    auth_api_client, fake_redis: FakeRedis, monkeypatch: pytest.MonkeyPatch
) -> None:
    from services.auth_service import InvalidCredentials

    calls = 0

    async def always_fail(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise InvalidCredentials

    monkeypatch.setattr("api.auth.authenticate_user", always_fail)
    for _ in range(5):
        response = await auth_api_client.client.post(
            "/api/auth/login",
            json={"email": "student@example.com", "password": "learning2026"},
        )
        assert response.status_code == 401

    limited = await auth_api_client.client.post(
        "/api/auth/login",
        json={"email": "student@example.com", "password": "learning2026"},
    )

    assert calls == 5
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "AUTH_RATE_LIMITED"
    assert limited.headers["retry-after"] == "900"


@pytest.mark.asyncio
async def test_registration_route_limits_before_the_sixth_service_call(
    auth_api_client, fake_redis: FakeRedis, monkeypatch: pytest.MonkeyPatch
) -> None:
    from services.auth_service import EmailAlreadyRegistered

    calls = 0

    async def always_fail(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise EmailAlreadyRegistered

    monkeypatch.setattr("api.auth.register_user", always_fail)
    for index in range(5):
        response = await auth_api_client.client.post(
            "/api/auth/register",
            json={
                "email": f"student{index}@example.com",
                "nickname": "Student",
                "password": "learning2026",
            },
        )
        assert response.status_code == 409

    limited = await auth_api_client.client.post(
        "/api/auth/register",
        json={
            "email": "student6@example.com",
            "nickname": "Student",
            "password": "learning2026",
        },
    )

    assert calls == 5
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "3600"


@pytest.mark.asyncio
async def test_refresh_route_uses_its_session_key_for_rate_limiting(
    auth_api_client, fake_redis: FakeRedis, monkeypatch: pytest.MonkeyPatch
) -> None:
    from services.auth_service import InvalidRefreshToken

    calls = 0

    async def always_fail(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise InvalidRefreshToken

    monkeypatch.setattr("api.auth.rotate_refresh_token", always_fail)
    for _ in range(30):
        response = await auth_api_client.client.post(
            "/api/auth/refresh",
            headers={"Cookie": "eduflow_refresh=valid-session-key"},
        )
        assert response.status_code == 401

    limited = await auth_api_client.client.post(
        "/api/auth/refresh",
        headers={"Cookie": "eduflow_refresh=valid-session-key"},
    )

    assert calls == 30
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "60"


@pytest.mark.asyncio
async def test_redis_outage_returns_a_retryable_service_unavailable_error(
    auth_api_client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("api.auth.get_redis", lambda: UnavailableRedis())

    response = await auth_api_client.client.post(
        "/api/auth/register",
        json={
            "email": "student@example.com",
            "nickname": "Student",
            "password": "learning2026",
        },
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AUTH_RATE_LIMIT_UNAVAILABLE"
    assert response.headers["retry-after"] == "1"


@pytest.mark.asyncio
async def test_redis_lifecycle_reuses_and_closes_the_shared_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from db import redis as redis_db

    class CloseableRedis:
        closed = False

        async def aclose(self) -> None:
            self.closed = True

    client = CloseableRedis()
    redis_db._redis = None
    monkeypatch.setattr(redis_db, "get_settings", lambda: SimpleNamespace(redis_url="redis://test"))
    monkeypatch.setattr(redis_db.Redis, "from_url", lambda *_args, **_kwargs: client)

    assert redis_db.get_redis() is client
    assert redis_db.get_redis() is client
    await redis_db.close_redis()

    assert client.closed is True
    assert redis_db._redis is None


def test_client_ip_ignores_forwarded_header_unless_peer_is_trusted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from starlette.requests import Request

    from api.auth import _client_ip

    scope = {
        "type": "http",
        "method": "POST",
        "scheme": "https",
        "path": "/api/auth/login",
        "raw_path": b"/api/auth/login",
        "query_string": b"",
        "headers": [(b"x-forwarded-for", b"203.0.113.10, 10.0.0.1")],
        "client": ("10.0.0.1", 12345),
        "server": ("testserver", 443),
    }
    request = Request(scope)

    monkeypatch.setattr(
        "api.auth.get_settings", lambda: SimpleNamespace(auth_trusted_proxy_ips=[])
    )
    assert _client_ip(request) == "10.0.0.1"

    monkeypatch.setattr(
        "api.auth.get_settings",
        lambda: SimpleNamespace(auth_trusted_proxy_ips=["10.0.0.1"]),
    )
    assert _client_ip(request) == "203.0.113.10"


@pytest.fixture
def auth_contract_client() -> TestClient:
    app = FastAPI()
    register_error_handlers(app)

    error_factories = {
        "email-registered": email_registered,
        "invalid-credentials": invalid_credentials,
        "access-token-invalid": access_token_invalid,
        "refresh-token-invalid": refresh_token_invalid,
        "account-disabled": account_disabled,
        "auth-rate-limited": auth_rate_limited,
    }
    for name, factory in error_factories.items():
        async def raise_auth_error(error_factory=factory) -> None:
            raise error_factory()

        app.add_api_route(f"/errors/{name}", raise_auth_error, methods=["GET"])

    @app.post("/register")
    async def register(request: RegisterRequest) -> dict[str, str]:
        return {"nickname": request.nickname}

    return TestClient(app)


def test_register_request_normalizes_nickname() -> None:
    request = RegisterRequest(
        email="student@example.com",
        nickname="  小明  ",
        password="learning2026",
    )

    assert request.nickname == "小明"


def test_register_request_rejects_bad_password() -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(
            email="student@example.com",
            nickname="小明",
            password="password",
        )


@pytest.mark.parametrize("nickname", ["", "   "])
def test_register_request_rejects_blank_nickname(nickname: str) -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(
            email="student@example.com",
            nickname=nickname,
            password="learning2026",
        )


def test_login_request_does_not_apply_registration_password_policy() -> None:
    request = LoginRequest(email="student@example.com", password="password")

    assert request.password == "password"


def test_login_request_allows_a_128_character_password() -> None:
    request = LoginRequest(email="student@example.com", password="a" * 128)

    assert request.password == "a" * 128


def test_login_request_rejects_password_longer_than_128_characters() -> None:
    with pytest.raises(ValidationError):
        LoginRequest(email="student@example.com", password="a" * 129)


def test_login_request_rejects_password_larger_than_256_utf8_bytes() -> None:
    with pytest.raises(ValidationError):
        LoginRequest(email="student@example.com", password="密" * 86)


def test_login_request_declares_the_128_character_openapi_bound() -> None:
    password_schema = LoginRequest.model_json_schema()["properties"]["password"]

    assert password_schema["maxLength"] == 128


def test_auth_response_serializes_user_without_sensitive_fields() -> None:
    user = UserResponse(
        id=uuid4(),
        email="student@example.com",
        nickname="小明",
        is_active=True,
        created_at=datetime(2026, 7, 24, tzinfo=timezone.utc),
    )
    response = AuthResponse(access_token="access-token", expires_in=900, user=user)

    assert response.token_type == "bearer"
    assert response.model_dump().keys() == {
        "access_token",
        "token_type",
        "expires_in",
        "user",
    }


@pytest.mark.parametrize(
    ("factory", "status_code", "code", "message", "headers"),
    [
        (email_registered, 409, "EMAIL_ALREADY_REGISTERED", "邮箱已注册", None),
        (
            invalid_credentials,
            401,
            "INVALID_CREDENTIALS",
            "邮箱或密码错误",
            {"WWW-Authenticate": "Bearer"},
        ),
        (
            access_token_invalid,
            401,
            "ACCESS_TOKEN_INVALID",
            "访问令牌无效或已过期",
            {"WWW-Authenticate": "Bearer"},
        ),
        (
            refresh_token_invalid,
            401,
            "REFRESH_TOKEN_INVALID",
            "刷新令牌无效或已过期",
            {"WWW-Authenticate": "Bearer"},
        ),
        (account_disabled, 403, "ACCOUNT_DISABLED", "账号已被禁用", None),
        (
            password_policy_violation,
            400,
            "PASSWORD_POLICY_VIOLATION",
            "密码不符合规则",
            None,
        ),
        (
            auth_rate_limited,
            429,
            "AUTH_RATE_LIMITED",
            "认证请求过于频繁，请稍后重试",
            None,
        ),
    ],
)
def test_auth_error_contracts(
    factory,
    status_code: int,
    code: str,
    message: str,
    headers: dict[str, str] | None,
) -> None:
    error = factory()

    assert error.status_code == status_code
    assert error.detail == {"error": {"code": code, "message": message}}
    assert error.headers == headers


@pytest.mark.parametrize(
    ("path", "status_code", "code", "message", "authenticate_header"),
    [
        (
            "/errors/email-registered",
            409,
            "EMAIL_ALREADY_REGISTERED",
            "邮箱已注册",
            None,
        ),
        (
            "/errors/invalid-credentials",
            401,
            "INVALID_CREDENTIALS",
            "邮箱或密码错误",
            "Bearer",
        ),
        (
            "/errors/access-token-invalid",
            401,
            "ACCESS_TOKEN_INVALID",
            "访问令牌无效或已过期",
            "Bearer",
        ),
        (
            "/errors/refresh-token-invalid",
            401,
            "REFRESH_TOKEN_INVALID",
            "刷新令牌无效或已过期",
            "Bearer",
        ),
        (
            "/errors/account-disabled",
            403,
            "ACCOUNT_DISABLED",
            "账号已被禁用",
            None,
        ),
        (
            "/errors/auth-rate-limited",
            429,
            "AUTH_RATE_LIMITED",
            "认证请求过于频繁，请稍后重试",
            None,
        ),
    ],
)
def test_live_auth_error_contracts_preserve_status_body_and_headers(
    auth_contract_client: TestClient,
    path: str,
    status_code: int,
    code: str,
    message: str,
    authenticate_header: str | None,
) -> None:
    response = auth_contract_client.get(path)

    assert response.status_code == status_code
    assert response.json() == {"error": {"code": code, "message": message}}
    assert response.headers.get("WWW-Authenticate") == authenticate_header


def test_live_weak_registration_password_returns_password_policy_contract(
    auth_contract_client: TestClient,
) -> None:
    response = auth_contract_client.post(
        "/register",
        json={
            "email": "student@example.com",
            "nickname": "小明",
            "password": "password",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "PASSWORD_POLICY_VIOLATION",
            "message": "密码不符合规则",
        }
    }


def test_live_non_password_validation_error_remains_a_422(
    auth_contract_client: TestClient,
) -> None:
    response = auth_contract_client.post(
        "/register",
        json={
            "email": "student@example.com",
            "nickname": "   ",
            "password": "learning2026",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
