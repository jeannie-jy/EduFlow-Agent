from __future__ import annotations

import uuid
from datetime import datetime
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import schema, select, types
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from db.models import AuthSession, Base, User
from schema.auth import LoginRequest, RegisterRequest
from security.passwords import hash_password
from security.tokens import hash_refresh_token
from services.auth_service import (
    EmailAlreadyRegistered,
    InvalidCredentials,
    authenticate_user,
    register_user,
)


def _make_sqlite_compatible() -> None:
    """Adapt PostgreSQL-only model types for the isolated service database."""
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, (JSONB, ARRAY)):
                column.type = types.JSON()
            elif isinstance(column.type, PG_UUID):
                column.type = types.Uuid(as_uuid=True)
                column.server_default = None
                if column.default is None and column.primary_key:
                    column.default = schema.ColumnDefault(uuid.uuid4)


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    _make_sqlite_compatible()
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def _create_user(
    session: AsyncSession,
    *,
    email: str = "student@example.com",
    password_hash: str | None = None,
    is_active: bool = True,
) -> User:
    user = User(
        id=uuid.uuid4(),
        email=email,
        email_normalized=email.casefold(),
        nickname="Student",
        password_hash=password_hash or "not-used",
        is_active=is_active,
    )
    session.add(user)
    await session.flush()
    return user


@pytest.mark.asyncio
async def test_register_creates_normalized_user_session_and_tokens(db_session: AsyncSession) -> None:
    result = await register_user(
        db_session,
        RegisterRequest(
            email="Student@Example.com",
            nickname="Student",
            password="learning2026",
        ),
        "pytest",
    )

    auth_session = await db_session.scalar(select(AuthSession))

    assert result.user.email_normalized == "student@example.com"
    assert result.user.password_hash != "learning2026"
    assert result.access_token.expires_in == 900
    assert auth_session is not None
    assert auth_session.user_id == result.user.id
    assert auth_session.user_agent == "pytest"
    assert auth_session.refresh_token_hash == hash_refresh_token(result.refresh_token)


@pytest.mark.asyncio
async def test_register_rejects_duplicate_normalized_email(db_session: AsyncSession) -> None:
    await _create_user(db_session, email="student@example.com")

    with pytest.raises(EmailAlreadyRegistered):
        await register_user(
            db_session,
            RegisterRequest(
                email="Student@Example.com",
                nickname="Another student",
                password="learning2026",
            ),
            "pytest",
        )


class _NamedUniqueViolation(Exception):
    diag = SimpleNamespace(constraint_name="uq_users_email_normalized")


class _RacingRegistrationSession:
    """Represent another transaction winning the insert race after lookup."""

    async def scalar(self, statement):
        return None

    def add_all(self, instances) -> None:
        return None

    def begin_nested(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> bool:
        return False

    async def flush(self) -> None:
        raise IntegrityError("INSERT", {}, _NamedUniqueViolation())


@pytest.mark.asyncio
async def test_register_converts_named_unique_race_to_duplicate_error() -> None:
    with pytest.raises(EmailAlreadyRegistered):
        await register_user(
            _RacingRegistrationSession(),
            RegisterRequest(
                email="student@example.com",
                nickname="Student",
                password="learning2026",
            ),
            None,
        )


@pytest.mark.asyncio
async def test_login_rejects_unknown_email_with_generic_error(db_session: AsyncSession) -> None:
    with pytest.raises(InvalidCredentials):
        await authenticate_user(
            db_session,
            LoginRequest(email="missing@example.com", password="learning2026"),
            "pytest",
        )


@pytest.mark.asyncio
async def test_login_rejects_wrong_password_with_generic_error(db_session: AsyncSession) -> None:
    await _create_user(db_session, password_hash=hash_password("learning2026"))

    with pytest.raises(InvalidCredentials):
        await authenticate_user(
            db_session,
            LoginRequest(email="student@example.com", password="wrong2026"),
            "pytest",
        )


@pytest.mark.asyncio
async def test_login_rejects_inactive_user_with_generic_error(db_session: AsyncSession) -> None:
    await _create_user(
        db_session,
        password_hash=hash_password("learning2026"),
        is_active=False,
    )

    with pytest.raises(InvalidCredentials):
        await authenticate_user(
            db_session,
            LoginRequest(email="student@example.com", password="learning2026"),
            "pytest",
        )


@pytest.mark.asyncio
async def test_login_updates_last_login_creates_session_and_rehashes_password(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = await _create_user(db_session, password_hash="legacy-password-hash")
    monkeypatch.setattr(
        "services.auth_service.verify_password", lambda password, encoded: (True, "upgraded-password-hash")
    )

    result = await authenticate_user(
        db_session,
        LoginRequest(email="Student@Example.com", password="learning2026"),
        "pytest",
    )
    await db_session.refresh(user)
    auth_session = await db_session.scalar(select(AuthSession))

    assert result.user.id == user.id
    assert result.access_token.expires_in == 900
    assert result.refresh_token
    assert user.password_hash == "upgraded-password-hash"
    assert isinstance(user.last_login_at, datetime)
    assert auth_session is not None
    assert auth_session.user_id == user.id
