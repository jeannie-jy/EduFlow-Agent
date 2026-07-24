"""HTTP routes for email/password authentication."""

from __future__ import annotations

import ipaddress
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth_errors import (
    auth_rate_limit_unavailable,
    auth_rate_limited,
    email_registered,
    invalid_credentials,
    refresh_token_invalid,
)
from api.deps import CurrentUser
from config import get_settings
from db.database import get_session
from db.redis import get_redis
from schema.auth import AuthResponse, LoginRequest, RegisterRequest, UserResponse
from security.passwords import normalize_email
from services.auth_rate_limit import (
    AuthRateLimitUnavailable,
    AuthRateLimited,
    check_login_limit,
    check_refresh_limit,
    check_registration_limit,
    clear_login_failures,
    login_attempt_lock,
    record_login_failure,
)
from services.auth_service import (
    EmailAlreadyRegistered,
    InvalidCredentials,
    InvalidRefreshToken,
    authenticate_user,
    get_refresh_rate_limit_identity,
    register_user,
    revoke_all_user_sessions,
    revoke_refresh_token,
    rotate_refresh_token,
)


router = APIRouter(prefix="/auth", tags=["auth"])


def set_refresh_cookie(response: Response, token: str) -> None:
    """Set the browser-only cookie carrying the opaque refresh token."""
    settings = get_settings()
    response.set_cookie(
        key=settings.auth_refresh_cookie_name,
        value=token,
        max_age=settings.auth_refresh_token_days * 86400,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/api/auth",
    )


def clear_refresh_cookie(response: Response) -> None:
    """Remove the refresh cookie using the same scope and security flags."""
    settings = get_settings()
    response.delete_cookie(
        key=settings.auth_refresh_cookie_name,
        path="/api/auth",
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite=settings.auth_cookie_samesite,
    )


def _auth_response(result) -> AuthResponse:
    return AuthResponse(
        access_token=result.access_token.token,
        expires_in=result.access_token.expires_in,
        user=UserResponse.model_validate(result.user),
    )


def _invalid_refresh_response() -> JSONResponse:
    error = refresh_token_invalid()
    response = JSONResponse(
        status_code=error.status_code,
        content=error.detail,
        headers=error.headers,
    )
    clear_refresh_cookie(response)
    return response


def _require_trusted_cookie_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin is not None and origin not in get_settings().cors_allowed_origins:
        raise HTTPException(status_code=403, detail="请求来源不受信任")


def _user_agent(request: Request) -> str | None:
    user_agent = request.headers.get("user-agent")
    return user_agent[:500] if user_agent else None


def _client_ip(request: Request) -> str:
    """Resolve the client after removing only configured trusted proxy hops."""
    peer_ip = request.client.host if request.client is not None else "unknown"
    try:
        peer = ipaddress.ip_address(peer_ip)
        trusted_proxies = {
            ipaddress.ip_address(value)
            for value in get_settings().auth_trusted_proxy_ips
        }
    except ValueError:
        return peer_ip
    if peer not in trusted_proxies:
        return peer_ip
    forwarded_for = request.headers.get("x-forwarded-for")
    if not forwarded_for:
        return peer_ip
    try:
        forwarded_ips = [
            ipaddress.ip_address(value.strip())
            for value in forwarded_for.split(",")
        ]
    except ValueError:
        return peer_ip
    if not forwarded_ips:
        return peer_ip
    for candidate in reversed(forwarded_ips):
        if candidate not in trusted_proxies:
            return str(candidate)
    return peer_ip


def _raise_rate_limit_error(error: Exception) -> None:
    if isinstance(error, AuthRateLimited):
        raise auth_rate_limited(error.retry_after)
    raise auth_rate_limit_unavailable()


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthResponse:
    """Create an account and issue its initial access/refresh token pair."""
    try:
        await check_registration_limit(get_redis(), _client_ip(request))
    except (AuthRateLimited, AuthRateLimitUnavailable) as error:
        _raise_rate_limit_error(error)
    try:
        result = await register_user(session, payload, _user_agent(request))
    except EmailAlreadyRegistered:
        raise email_registered()
    set_refresh_cookie(response, result.refresh_token)
    return _auth_response(result)


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthResponse:
    """Verify credentials and issue a new access/refresh token pair."""
    client_ip = _client_ip(request)
    normalized_email = normalize_email(str(payload.email))
    redis = get_redis()
    try:
        async with login_attempt_lock(redis, client_ip, normalized_email):
            await check_login_limit(redis, client_ip, normalized_email)
            try:
                result = await authenticate_user(session, payload, _user_agent(request))
            except InvalidCredentials:
                await record_login_failure(redis, client_ip, normalized_email)
                raise invalid_credentials()
            await clear_login_failures(redis, client_ip, normalized_email)
    except (AuthRateLimited, AuthRateLimitUnavailable) as error:
        _raise_rate_limit_error(error)
    set_refresh_cookie(response, result.refresh_token)
    return _auth_response(result)


@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthResponse | JSONResponse:
    """Rotate a valid refresh session and return a replacement token pair."""
    _require_trusted_cookie_origin(request)
    settings = get_settings()
    raw_token = request.cookies.get(settings.auth_refresh_cookie_name)
    if not raw_token:
        return _invalid_refresh_response()
    family_id = await get_refresh_rate_limit_identity(session, raw_token)
    rate_limit_identity = (
        f"family:{family_id}" if family_id is not None else f"ip:{_client_ip(request)}"
    )
    try:
        await check_refresh_limit(get_redis(), rate_limit_identity)
    except (AuthRateLimited, AuthRateLimitUnavailable) as error:
        _raise_rate_limit_error(error)
    try:
        result = await rotate_refresh_token(session, raw_token, _user_agent(request))
    except InvalidRefreshToken:
        return _invalid_refresh_response()
    set_refresh_cookie(response, result.refresh_token)
    return _auth_response(result)


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    """Revoke the current refresh session, without revealing its validity."""
    _require_trusted_cookie_origin(request)
    raw_token = request.cookies.get(get_settings().auth_refresh_cookie_name)
    if raw_token:
        await revoke_refresh_token(session, raw_token)
    clear_refresh_cookie(response)


@router.post("/logout-all", status_code=204)
async def logout_all(
    response: Response,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    """Revoke all active refresh sessions belonging to the current user."""
    await revoke_all_user_sessions(session, current_user.id)
    clear_refresh_cookie(response)


@router.get("/me", response_model=UserResponse)
async def me(current_user: CurrentUser) -> UserResponse:
    """Return the public profile for the bearer-token principal."""
    return UserResponse.model_validate(current_user)
