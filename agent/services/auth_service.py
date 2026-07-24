"""Registration and password-login service operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import uuid

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from db.models import AuthSession, User
from schema.auth import LoginRequest, RegisterRequest
from security.passwords import (
    DUMMY_PASSWORD_HASH,
    hash_password,
    normalize_email,
    verify_password,
)
from security.tokens import (
    IssuedAccessToken,
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
)


_EMAIL_UNIQUE_CONSTRAINT = "uq_users_email_normalized"


@dataclass(frozen=True)
class AuthResult:
    """Tokens and principal issued after a successful authentication flow."""

    user: User
    access_token: IssuedAccessToken
    refresh_token: str


class EmailAlreadyRegistered(Exception):
    """Raised when a normalized email already belongs to an account."""


class InvalidCredentials(Exception):
    """Raised for all failed password-login attempts."""


class InvalidRefreshToken(Exception):
    """Reserved for refresh-token validation and rotation flows."""


def _create_refresh_session(
    user_id: uuid.UUID,
    user_agent: str | None,
    family_id: uuid.UUID | None = None,
) -> tuple[str, AuthSession]:
    """Create an opaque refresh token and the corresponding database record."""
    settings = get_settings()
    raw_token = generate_refresh_token()
    auth_session = AuthSession(
        id=uuid.uuid4(),
        user_id=user_id,
        family_id=family_id or uuid.uuid4(),
        refresh_token_hash=hash_refresh_token(raw_token),
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.auth_refresh_token_days),
        user_agent=user_agent,
    )
    return raw_token, auth_session


def _is_email_unique_violation(error: IntegrityError) -> bool:
    """Return whether a database insert lost the normalized-email race."""
    original = error.orig
    constraint_name = getattr(getattr(original, "diag", None), "constraint_name", None)
    if constraint_name is not None:
        return constraint_name == _EMAIL_UNIQUE_CONSTRAINT
    return _EMAIL_UNIQUE_CONSTRAINT in str(original) or "users.email_normalized" in str(
        original
    )


async def _lock_user(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    """Serialize refresh-token changes for one user before mutating sessions."""
    return await session.scalar(
        select(User).where(User.id == user_id).with_for_update()
    )


async def register_user(
    session: AsyncSession,
    request: RegisterRequest,
    user_agent: str | None,
) -> AuthResult:
    """Register an account and issue its first access and refresh tokens."""
    normalized_email = normalize_email(str(request.email))
    existing_user = await session.scalar(
        select(User).where(User.email_normalized == normalized_email)
    )
    if existing_user is not None:
        raise EmailAlreadyRegistered

    user = User(
        id=uuid.uuid4(),
        email=str(request.email),
        email_normalized=normalized_email,
        nickname=request.nickname,
        password_hash=hash_password(request.password),
    )
    refresh_token, auth_session = _create_refresh_session(user.id, user_agent)

    try:
        async with session.begin_nested():
            session.add_all((user, auth_session))
            await session.flush()
    except IntegrityError as error:
        if _is_email_unique_violation(error):
            raise EmailAlreadyRegistered from error
        raise

    return AuthResult(
        user=user,
        access_token=create_access_token(user.id, auth_session.id),
        refresh_token=refresh_token,
    )


async def authenticate_user(
    session: AsyncSession,
    request: LoginRequest,
    user_agent: str | None,
) -> AuthResult:
    """Authenticate an active user and issue a new token pair."""
    normalized_email = normalize_email(str(request.email))
    user = await session.scalar(select(User).where(User.email_normalized == normalized_email))

    valid, replacement_hash = verify_password(
        request.password,
        user.password_hash if user is not None else DUMMY_PASSWORD_HASH,
    )
    if user is None or not valid or not user.is_active:
        raise InvalidCredentials

    if replacement_hash is not None:
        user.password_hash = replacement_hash
    user.last_login_at = datetime.now(timezone.utc)
    refresh_token, auth_session = _create_refresh_session(user.id, user_agent)
    session.add(auth_session)
    await session.flush()

    return AuthResult(
        user=user,
        access_token=create_access_token(user.id, auth_session.id),
        refresh_token=refresh_token,
    )


async def rotate_refresh_token(
    session: AsyncSession,
    raw_token: str,
    user_agent: str | None,
) -> AuthResult:
    """Rotate one valid refresh token and preserve its session family."""
    token_hash = hash_refresh_token(raw_token)
    user_id = await session.scalar(
        select(AuthSession.user_id).where(AuthSession.refresh_token_hash == token_hash)
    )
    if user_id is None:
        raise InvalidRefreshToken

    user = await _lock_user(session, user_id)
    if user is None:
        raise InvalidRefreshToken

    record = await session.scalar(
        select(AuthSession)
        .where(AuthSession.refresh_token_hash == token_hash)
        .with_for_update()
    )
    if record is None:
        raise InvalidRefreshToken

    if record.replaced_by_id is not None:
        await revoke_session_family(session, record.family_id)
        await session.commit()
        raise InvalidRefreshToken

    now = datetime.now(timezone.utc)
    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if record.revoked_at is not None or expires_at <= now:
        raise InvalidRefreshToken

    if not user.is_active:
        raise InvalidRefreshToken

    refresh_token, replacement = _create_refresh_session(
        user.id,
        user_agent,
        family_id=record.family_id,
    )
    session.add(replacement)
    await session.flush()
    record.replaced_by_id = replacement.id
    record.last_used_at = now
    record.revoked_at = now

    return AuthResult(
        user=user,
        access_token=create_access_token(user.id, replacement.id),
        refresh_token=refresh_token,
    )


async def revoke_refresh_token(session: AsyncSession, raw_token: str) -> None:
    """Revoke a refresh token without revealing whether it existed."""
    token_hash = hash_refresh_token(raw_token)
    user_id = await session.scalar(
        select(AuthSession.user_id).where(AuthSession.refresh_token_hash == token_hash)
    )
    if user_id is None or await _lock_user(session, user_id) is None:
        return

    record = await session.scalar(
        select(AuthSession)
        .where(AuthSession.refresh_token_hash == token_hash)
        .with_for_update()
    )
    if record is None or record.revoked_at is not None:
        return

    record.revoked_at = datetime.now(timezone.utc)


async def revoke_all_user_sessions(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Revoke every active refresh session belonging to one user."""
    if await _lock_user(session, user_id) is None:
        return

    await session.execute(
        update(AuthSession)
        .where(
            AuthSession.user_id == user_id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(timezone.utc))
    )


async def revoke_session_family(session: AsyncSession, family_id: uuid.UUID) -> None:
    """Revoke every active refresh session in one rotation family."""
    user_id = await session.scalar(
        select(AuthSession.user_id).where(AuthSession.family_id == family_id)
    )
    if user_id is None or await _lock_user(session, user_id) is None:
        return

    await session.execute(
        update(AuthSession)
        .where(
            AuthSession.family_id == family_id,
            AuthSession.user_id == user_id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(timezone.utc))
    )
