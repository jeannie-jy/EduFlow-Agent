"""Backend authentication with opaque HttpOnly cookie sessions."""

from __future__ import annotations

import re
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

COOKIE_NAME = "eduflow_session"
_DUMMY_PASSWORD_HASH = hash_password("constant-time-invalid-user")
router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    nickname: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=200)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=200)


def _normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
        raise HTTPException(status_code=422, detail="Invalid email address")
    return normalized


def _public_user(user: User) -> dict[str, str]:
    return {
        "id": str(user.id),
        "email": user.email,
        "nickname": user.nickname,
        "role": _user_role(user),
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
        if user is not None and _user_role(user) not in set(allowed_roles):
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user

    return dependency


require_editor = require_roles("teacher", "admin")


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
) -> dict[str, str]:
    settings = get_settings()
    retry_after = await check_rate_limit(
        "register",
        request.client.host if request.client else "unknown",
        limit=settings.auth_register_attempts,
        window_seconds=settings.auth_register_window_seconds,
    )
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="Too many registration attempts",
            headers={"Retry-After": str(retry_after)},
        )
    email = _normalize_email(body.email)
    user = User(
        id=uuid.uuid4(),
        email=email,
        nickname=body.nickname.strip(),
        password_hash=hash_password(body.password),
        role="teacher",
        is_active=True,
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Email already registered") from exc
    await _issue_session(user, response, session)
    record_audit(
        session,
        action="auth.register",
        resource_type="user",
        resource_id=str(user.id),
        actor_id=user.id,
    )
    return _public_user(user)


@router.post("/login")
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    settings = get_settings()
    email = _normalize_email(body.email)
    remote = request.client.host if request.client else "unknown"
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
    await _issue_session(user, response, session)
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
