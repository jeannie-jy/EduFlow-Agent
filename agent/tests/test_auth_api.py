from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from api.auth_errors import (
    access_token_invalid,
    account_disabled,
    auth_rate_limited,
    email_registered,
    invalid_credentials,
    refresh_token_invalid,
)
from schema.auth import AuthResponse, LoginRequest, RegisterRequest, UserResponse


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
