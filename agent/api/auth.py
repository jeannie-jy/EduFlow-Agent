"""Backend authentication with opaque HttpOnly cookie sessions."""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from db.database import get_session
from db.models import AuthSession, User
from services.audit import record_audit
from services.auth_service import (
    hash_password,
    hash_session_token,
    new_session_token,
    verify_password,
)
from services.rate_limit import check_rate_limit
from services.request_security import client_ip

COOKIE_NAME = "eduflow_session"
CSRF_COOKIE_NAME = "eduflow_csrf"
DEVICE_COOKIE_NAME = "eduflow_device"
CURRENT_POLICY_VERSION = "2026-09-14"
_DUMMY_PASSWORD_HASH = hash_password("constant-time-invalid-user")
router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    nickname: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=200)
    accepted_terms: bool = False
    policy_version: str = Field(default=CURRENT_POLICY_VERSION, min_length=1, max_length=50)
    registration_challenge: str | None = Field(default=None, max_length=1000)
    registration_solution: str | None = Field(default=None, max_length=100)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=200)
    totp_code: str | None = Field(default=None, min_length=6, max_length=12)


class TokenRequest(BaseModel):
    token: str = Field(min_length=20, max_length=500)


class PasswordResetRequest(TokenRequest):
    password: str = Field(min_length=8, max_length=200)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


class EmailRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)


def _challenge_signature(payload: str) -> str:
    secret = get_settings().auth_registration_challenge_secret
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def _issue_registration_challenge() -> dict[str, object]:
    settings = get_settings()
    expires = int(datetime.now(timezone.utc).timestamp()) + 600
    payload = f"{secrets.token_urlsafe(18)}.{expires}.{settings.auth_registration_challenge_difficulty}"
    encoded = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    signature = _challenge_signature(payload) if settings.auth_registration_challenge_secret else "dev"
    return {"challenge": f"{encoded}.{signature}", "difficulty": settings.auth_registration_challenge_difficulty, "expires_at": expires}


def _validate_registration_challenge(challenge: str | None, solution: str | None) -> None:
    settings = get_settings()
    if not settings.auth_registration_challenge_required:
        return
    if not challenge or not solution:
        raise HTTPException(status_code=422, detail="Registration challenge is required")
    try:
        encoded, signature = challenge.split(".", 1)
        payload = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()
        nonce, expires_raw, difficulty_raw = payload.split(".")
        expires = int(expires_raw)
        difficulty = int(difficulty_raw)
    except (ValueError, TypeError, UnicodeError) as exc:
        raise HTTPException(status_code=422, detail="Invalid registration challenge") from exc
    if not settings.auth_registration_challenge_secret or not hmac.compare_digest(signature, _challenge_signature(payload)):
        raise HTTPException(status_code=422, detail="Invalid registration challenge")
    if expires < int(datetime.now(timezone.utc).timestamp()) or difficulty != settings.auth_registration_challenge_difficulty:
        raise HTTPException(status_code=422, detail="Expired registration challenge")
    if len(solution) > 100 or not hashlib.sha256(f"{nonce}{solution}".encode()).hexdigest().startswith("0" * difficulty):
        raise HTTPException(status_code=422, detail="Registration challenge failed")


def _normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
        raise HTTPException(status_code=422, detail="Invalid email address")
    return normalized


def _public_user(user: User) -> dict[str, object]:
    return {
        "id": str(user.id),
        "email": user.email,
        "nickname": user.nickname,
        "role": _user_role(user),
        "email_verified": user.email_verified_at is not None,
    }


def is_admin(user: User | None) -> bool:
    """Return whether a resolved user may administer resources across owners."""
    return user is not None and _user_role(user) == "admin"


def _user_role(user: User) -> str:
    role = getattr(user, "role", "teacher")
    return role if isinstance(role, str) else "teacher"


async def _issue_session(user: User, response: Response, session: AsyncSession) -> None:
    settings = get_settings()
    token = new_session_token()
    csrf_token = new_session_token()
    expires = datetime.now(timezone.utc) + timedelta(days=settings.auth_session_days)
    session.add(
        AuthSession(
            id=uuid.uuid4(),
            user_id=user.id,
            token_hash=hash_session_token(token),
            expires_at=expires,
        )
    )
    await session.flush()
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=settings.auth_session_days * 86400,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        csrf_token,
        max_age=settings.auth_session_days * 86400,
        httponly=False,
        secure=settings.auth_cookie_secure,
        samesite="strict",
        path="/",
    )


def _issue_device_cookie(request: Request, response: Response) -> str:
    """Issue a privacy-preserving anonymous device bucket for abuse controls.

    The value is a random opaque identifier and is never used for
    authentication.  IP and account limits remain authoritative when a client
    blocks or rotates cookies; this extra dimension only makes low-effort
    registration/login spraying more expensive.
    """
    value = request.cookies.get(DEVICE_COOKIE_NAME)
    if not value or len(value) > 128:
        value = secrets.token_urlsafe(24)
        response.set_cookie(
            DEVICE_COOKIE_NAME,
            value,
            max_age=90 * 86400,
            httponly=True,
            secure=get_settings().auth_cookie_secure,
            samesite="lax",
            path="/",
        )
    return value


async def get_current_user(
    token: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
    session: AsyncSession = Depends(get_session),
) -> User | None:
    settings = get_settings()
    if not token:
        if settings.auth_required:
            raise HTTPException(status_code=401, detail="Authentication required")
        return None
    result = await session.execute(
        select(User)
        .join(AuthSession, AuthSession.user_id == User.id)
        .where(
            AuthSession.token_hash == hash_session_token(token),
            AuthSession.expires_at > datetime.now(timezone.utc),
            User.is_active.is_(True),
        )
    )
    user = result.scalar_one_or_none()
    if user is None and settings.auth_required:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return user


def require_roles(*allowed_roles: str) -> Callable:
    """Dependency factory; anonymous local-dev mode remains backward compatible."""
    async def dependency(
        user: User | None = Depends(get_current_user),
    ) -> User | None:
        if user is not None:
            if _user_role(user) not in set(allowed_roles):
                raise HTTPException(status_code=403, detail="Insufficient role")
            if get_settings().auth_require_email_verification and user.email_verified_at is None:
                raise HTTPException(status_code=403, detail="Email verification required")
        return user

    return dependency


# Public SaaS members may create their own learning content. Roles still gate
# administration and cross-owner access; self-registration never grants either.
require_editor = require_roles("student", "teacher", "admin")


async def require_admin(
    user: User | None = Depends(get_current_user),
) -> User:
    """Require an authenticated administrator even in local optional-auth mode."""
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="Insufficient role")
    return user


async def require_project_owner(
    request: Request,
    user: User | None = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> User | None:
    """Apply owner isolation to every business route carrying ``project_id``."""
    raw_project_id = request.path_params.get("project_id")
    if user is None or raw_project_id is None:
        return user
    try:
        project_id = uuid.UUID(raw_project_id)
    except (TypeError, ValueError):
        return user  # The endpoint's canonical parser returns the public 422 shape.
    from db.models import Project

    project = await session.get(Project, project_id)
    if (
        project is not None
        and not is_admin(user)
        and project.owner_id != str(user.id)
    ):
        # Do not reveal whether another tenant owns the identifier.
        raise HTTPException(status_code=404, detail="Project not found")
    return user


@router.post("/register", status_code=201)
async def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    settings = get_settings()
    if not settings.auth_allow_registration:
        raise HTTPException(status_code=403, detail="Registration is disabled")
    email = _normalize_email(body.email)
    device_id = request.cookies.get(DEVICE_COOKIE_NAME, "")[:128]
    rate_checks = [
        await check_rate_limit(
            "register-ip",
            client_ip(request),
            limit=settings.auth_register_attempts,
            window_seconds=settings.auth_register_window_seconds,
        )
    ]
    if device_id:
        rate_checks.append(
            await check_rate_limit(
                "register-device",
                device_id,
                limit=settings.auth_register_attempts,
                window_seconds=settings.auth_register_window_seconds,
            )
        )
    rate_checks.append(
        await check_rate_limit(
            "register-account",
            email,
            limit=settings.auth_register_attempts,
            window_seconds=settings.auth_register_window_seconds,
        )
    )
    retry_after = max((value for value in rate_checks if value is not None), default=None)
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="Too many registration attempts",
            headers={"Retry-After": str(retry_after)},
        )
    _validate_registration_challenge(body.registration_challenge, body.registration_solution)
    if not body.accepted_terms:
        raise HTTPException(status_code=422, detail="Service terms and privacy policy must be accepted")
    if body.policy_version != CURRENT_POLICY_VERSION:
        raise HTTPException(status_code=422, detail="Please accept the latest service terms and privacy policy")
    if not re.search(r"[A-Za-z]", body.password) or not re.search(r"\d", body.password):
        raise HTTPException(status_code=422, detail="Password must contain letters and numbers")
    user = User(
        id=uuid.uuid4(),
        email=email,
        nickname=body.nickname.strip(),
        password_hash=hash_password(body.password),
        role="student",
        is_active=True,
        email_verified_at=(
            None if settings.auth_require_email_verification else datetime.now(timezone.utc)
        ),
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Email already registered") from exc
    from db.models import UserConsent
    for policy in ("terms", "privacy"):
        session.add(UserConsent(
            id=uuid.uuid4(), user_id=user.id, policy=policy,
            policy_version=body.policy_version,
        ))
    if settings.auth_require_email_verification:
        from services.account_email import create_one_time_token, send_account_email
        token = await create_one_time_token(session, user, "verify_email")
        await send_account_email(user, token, "verify_email")
    await _issue_session(user, response, session)
    _issue_device_cookie(request, response)
    record_audit(
        session,
        action="auth.register",
        resource_type="user",
        resource_id=str(user.id),
        actor_id=user.id,
    )
    return _public_user(user)


@router.get("/registration-challenge")
async def registration_challenge() -> dict[str, object]:
    settings = get_settings()
    if not settings.auth_allow_registration:
        raise HTTPException(status_code=403, detail="Registration is disabled")
    return _issue_registration_challenge()


@router.post("/login")
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    settings = get_settings()
    email = _normalize_email(body.email)
    remote = client_ip(request)
    retry_values = [
        await check_rate_limit(
            "login-ip",
            remote,
            limit=settings.auth_login_attempts,
            window_seconds=settings.auth_login_window_seconds,
        ),
        await check_rate_limit(
            "login-account",
            email,
            limit=settings.auth_login_attempts,
            window_seconds=settings.auth_login_window_seconds,
        ),
    ]
    device_id = request.cookies.get(DEVICE_COOKIE_NAME, "")[:128]
    if device_id:
        retry_values.append(
            await check_rate_limit(
                "login-device",
                device_id,
                limit=settings.auth_login_attempts,
                window_seconds=settings.auth_login_window_seconds,
            )
        )
    retry_after = max((value for value in retry_values if value is not None), default=None)
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts",
            headers={"Retry-After": str(retry_after)},
        )
    user = await session.scalar(select(User).where(User.email == email))
    candidate_hash = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
    password_valid = verify_password(body.password, candidate_hash)
    if user is None or not user.is_active or not password_valid:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if user.role == "admin":
        from db.models import UserMFA
        from services.totp import verify_code
        mfa = await session.get(UserMFA, user.id)
        if mfa is not None and mfa.enabled:
            if not body.totp_code:
                raise HTTPException(status_code=401, detail="MFA code required")
            from services.provider_credentials import decrypt_user_secret
            try:
                secret = await decrypt_user_secret(
                    user_id=user.id, purpose="totp",
                    ciphertext=mfa.secret_ciphertext,
                    encrypted_data_key=mfa.secret_encrypted_data_key,
                    nonce=mfa.secret_nonce,
                    key_version=mfa.kms_key_version,
                )
            except Exception as exc:
                raise HTTPException(status_code=503, detail="MFA service unavailable") from exc
            if not verify_code(secret, body.totp_code):
                raise HTTPException(status_code=401, detail="Invalid MFA code")
    await _issue_session(user, response, session)
    _issue_device_cookie(request, response)
    record_audit(
        session,
        action="auth.login",
        resource_type="user",
        resource_id=str(user.id),
        actor_id=user.id,
    )
    return _public_user(user)


@router.get("/me")
async def me(user: User | None = Depends(get_current_user)) -> dict[str, str]:
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return _public_user(user)


@router.post("/request-email-verification", status_code=202)
async def request_email_verification(
    request: Request,
    user: User | None = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if user.email_verified_at is not None:
        return {"status": "already_verified"}
    retry_after = await check_rate_limit(
        "verification-email", f"{user.id}:{client_ip(request)}", limit=3, window_seconds=3600
    )
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="Too many verification emails",
            headers={"Retry-After": str(retry_after)},
        )
    from services.account_email import create_one_time_token, send_account_email
    token = await create_one_time_token(session, user, "verify_email")
    await send_account_email(user, token, "verify_email")
    return {"status": "sent"}


@router.post("/verify-email")
async def verify_email(
    body: TokenRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    from db.models import AuthOneTimeToken
    from services.account_email import hash_one_time_token
    now = datetime.now(timezone.utc)
    token = await session.scalar(select(AuthOneTimeToken).where(
        AuthOneTimeToken.token_hash == hash_one_time_token(body.token),
        AuthOneTimeToken.purpose == "verify_email",
        AuthOneTimeToken.consumed_at.is_(None),
        AuthOneTimeToken.expires_at > now,
    ).with_for_update())
    if token is None:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")
    user = await session.get(User, token.user_id)
    if user is None:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")
    user.email_verified_at = now
    token.consumed_at = now
    record_audit(session, action="auth.email_verified", resource_type="user", resource_id=str(user.id), actor_id=user.id)
    return {"status": "verified"}


@router.post("/forgot-password", status_code=202)
async def forgot_password(
    body: EmailRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    retry_after = await check_rate_limit(
        "password-reset", client_ip(request), limit=5, window_seconds=3600
    )
    if retry_after is not None:
        raise HTTPException(status_code=429, detail="Too many password reset attempts", headers={"Retry-After": str(retry_after)})
    try:
        email = _normalize_email(body.email)
    except HTTPException:
        return {"status": "accepted"}
    user = await session.scalar(select(User).where(User.email == email, User.is_active.is_(True)))
    if user is not None:
        from services.account_email import create_one_time_token, send_account_email
        token = await create_one_time_token(session, user, "reset_password")
        await send_account_email(user, token, "reset_password")
    return {"status": "accepted"}


@router.post("/reset-password")
async def reset_password(
    body: PasswordResetRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    if not re.search(r"[A-Za-z]", body.password) or not re.search(r"\d", body.password):
        raise HTTPException(status_code=422, detail="Password must contain letters and numbers")
    from db.models import AuthOneTimeToken
    from services.account_email import hash_one_time_token
    now = datetime.now(timezone.utc)
    token = await session.scalar(select(AuthOneTimeToken).where(
        AuthOneTimeToken.token_hash == hash_one_time_token(body.token),
        AuthOneTimeToken.purpose == "reset_password",
        AuthOneTimeToken.consumed_at.is_(None),
        AuthOneTimeToken.expires_at > now,
    ).with_for_update())
    if token is None:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    user = await session.get(User, token.user_id)
    if user is None:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    user.password_hash = hash_password(body.password)
    token.consumed_at = now
    await session.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    record_audit(session, action="auth.password_reset", resource_type="user", resource_id=str(user.id), actor_id=user.id)
    return {"status": "reset"}


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User | None = Depends(get_current_user),
) -> dict[str, str]:
    """Change a signed-in user's password and revoke every old session."""
    user = current_user
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not re.search(r"[A-Za-z]", body.new_password) or not re.search(r"\d", body.new_password):
        raise HTTPException(status_code=422, detail="Password must contain letters and numbers")
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is invalid")
    user.password_hash = hash_password(body.new_password)
    await session.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    record_audit(
        session,
        action="auth.password_changed",
        resource_type="user",
        resource_id=str(user.id),
        actor_id=user.id,
    )
    return {"status": "changed", "message": "Password changed; sign in again on all devices"}


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    token: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
    session: AsyncSession = Depends(get_session),
) -> None:
    if token:
        await session.execute(
            delete(AuthSession).where(AuthSession.token_hash == hash_session_token(token))
        )
    response.delete_cookie(COOKIE_NAME, path="/", samesite="lax")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/", samesite="strict")
