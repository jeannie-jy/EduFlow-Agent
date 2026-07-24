from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

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
