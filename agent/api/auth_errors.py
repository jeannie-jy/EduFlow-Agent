"""Stable HTTP error contracts for authentication endpoints."""

from __future__ import annotations

from fastapi import HTTPException


def auth_http_error(
    status_code: int,
    code: str,
    message: str,
    headers: dict[str, str] | None = None,
) -> HTTPException:
    """Return an authentication error in the API's common error envelope."""
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message}},
        headers=headers,
    )


def email_registered() -> HTTPException:
    """Return the stable duplicate-registration error."""
    return auth_http_error(409, "EMAIL_ALREADY_REGISTERED", "邮箱已注册")


def password_policy_violation() -> HTTPException:
    """Return the stable error for a registration password policy violation."""
    return auth_http_error(400, "PASSWORD_POLICY_VIOLATION", "密码不符合规则")


def invalid_credentials() -> HTTPException:
    """Return a generic error that does not reveal account existence or status."""
    return auth_http_error(
        401,
        "INVALID_CREDENTIALS",
        "邮箱或密码错误",
        {"WWW-Authenticate": "Bearer"},
    )


def access_token_invalid() -> HTTPException:
    """Return the stable invalid-access-token error."""
    return auth_http_error(
        401,
        "ACCESS_TOKEN_INVALID",
        "访问令牌无效或已过期",
        {"WWW-Authenticate": "Bearer"},
    )


def refresh_token_invalid() -> HTTPException:
    """Return the stable invalid-refresh-token error."""
    return auth_http_error(
        401,
        "REFRESH_TOKEN_INVALID",
        "刷新令牌无效或已过期",
        {"WWW-Authenticate": "Bearer"},
    )


def account_disabled() -> HTTPException:
    """Return the stable error for a disabled authenticated account."""
    return auth_http_error(403, "ACCOUNT_DISABLED", "账号已被禁用")


def auth_rate_limited() -> HTTPException:
    """Return the stable authentication rate-limit error."""
    return auth_http_error(429, "AUTH_RATE_LIMITED", "认证请求过于频繁，请稍后重试")
