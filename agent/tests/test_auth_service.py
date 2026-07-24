from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
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
from security.tokens import decode_access_token, hash_refresh_token
from services.auth_service import (
    EmailAlreadyRegistered,
    InvalidCredentials,
    InvalidRefreshToken,
    authenticate_user,
    register_user,
    revoke_all_user_sessions,
    revoke_refresh_token,
    revoke_session_family,
    rotate_refresh_token,
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


@pytest_asyncio.fixture
async def registered_auth(db_session: AsyncSession):
    return await register_user(
        db_session,
        RegisterRequest(
            email="student@example.com",
            nickname="Student",
            password="learning2026",
        ),
        "pytest-register",
    )


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


def _statement_table_name(statement) -> str:
    """Return the table targeted by a SELECT or UPDATE statement."""
    table = getattr(statement, "table", None)
    if table is not None:
        return table.name
    return statement.get_final_froms()[0].name


class _LockRecordingSession:
    """Record SQL lock ordering while supplying complete auth entities."""

    def __init__(self) -> None:
        self.user = User(
            id=uuid.uuid4(),
            email="student@example.com",
            email_normalized="student@example.com",
            nickname="Student",
            password_hash="not-used",
            is_active=True,
        )
        self.record = AuthSession(
            id=uuid.uuid4(),
            user_id=self.user.id,
            family_id=uuid.uuid4(),
            refresh_token_hash="a" * 64,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        self.scalar_statements = []
        self.execute_statements = []

    async def scalar(self, statement):
        self.scalar_statements.append(statement)
        if _statement_table_name(statement) == "users":
            return self.user
        if list(statement.selected_columns)[0].key == "user_id":
            return self.user.id
        return self.record

    async def get(self, model, identity):
        return self.user

    def add(self, instance) -> None:
        return None

    async def flush(self) -> None:
        return None

    async def execute(self, statement) -> None:
        self.execute_statements.append(statement)


class _UnknownRefreshLockRecordingSession:
    """Record lock behavior for a refresh token that has no session record."""

    def __init__(self) -> None:
        self.scalar_statements = []

    async def scalar(self, statement):
        self.scalar_statements.append(statement)
        return None


def _lock_shapes(session: _LockRecordingSession | _UnknownRefreshLockRecordingSession):
    return [
        (
            _statement_table_name(statement),
            getattr(statement, "_for_update_arg", None) is not None,
        )
        for statement in session.scalar_statements
    ]


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
async def test_rotate_locks_user_before_relocking_refresh_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _LockRecordingSession()
    replacement = AuthSession(
        id=uuid.uuid4(),
        user_id=session.user.id,
        family_id=session.record.family_id,
        refresh_token_hash="b" * 64,
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    monkeypatch.setattr(
        "services.auth_service._create_refresh_session",
        lambda user_id, user_agent, family_id: ("replacement-token", replacement),
    )

    await rotate_refresh_token(session, "refresh-token", "pytest-refresh")

    assert _lock_shapes(session) == [
        ("auth_sessions", False),
        ("users", True),
        ("auth_sessions", True),
    ]


@pytest.mark.asyncio
async def test_single_logout_locks_user_before_relocking_refresh_session() -> None:
    session = _LockRecordingSession()

    await revoke_refresh_token(session, "refresh-token")

    assert _lock_shapes(session) == [
        ("auth_sessions", False),
        ("users", True),
        ("auth_sessions", True),
    ]


@pytest.mark.asyncio
async def test_family_revocation_locks_user_before_updating_sessions() -> None:
    session = _LockRecordingSession()

    await revoke_session_family(session, session.record.family_id)

    assert _lock_shapes(session) == [
        ("auth_sessions", False),
        ("users", True),
    ]
    assert [_statement_table_name(statement) for statement in session.execute_statements] == [
        "auth_sessions"
    ]


@pytest.mark.asyncio
async def test_logout_all_locks_user_before_updating_sessions() -> None:
    session = _LockRecordingSession()

    await revoke_all_user_sessions(session, session.user.id)

    assert _lock_shapes(session) == [("users", True)]
    assert [_statement_table_name(statement) for statement in session.execute_statements] == [
        "auth_sessions"
    ]


@pytest.mark.asyncio
async def test_unknown_refresh_token_does_not_acquire_user_or_session_locks() -> None:
    session = _UnknownRefreshLockRecordingSession()

    with pytest.raises(InvalidRefreshToken):
        await rotate_refresh_token(session, "unknown-refresh-token", "pytest-refresh")
    await revoke_refresh_token(session, "unknown-refresh-token")

    assert _lock_shapes(session) == [
        ("auth_sessions", False),
        ("auth_sessions", False),
    ]


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


@pytest.mark.asyncio
async def test_refresh_rotates_session(
    db_session: AsyncSession, registered_auth
) -> None:
    old = registered_auth

    result = await rotate_refresh_token(
        db_session,
        old.refresh_token,
        "pytest-refresh",
    )
    old_record = await db_session.get(
        AuthSession,
        decode_access_token(old.access_token.token).session_id,
    )
    replacement = await db_session.get(
        AuthSession,
        decode_access_token(result.access_token.token).session_id,
    )

    assert result.user.id == old.user.id
    assert result.refresh_token != old.refresh_token
    assert old_record is not None
    assert old_record.revoked_at is not None
    assert old_record.replaced_by_id == replacement.id
    assert replacement is not None
    assert replacement.family_id == old_record.family_id
    assert replacement.refresh_token_hash == hash_refresh_token(result.refresh_token)
    assert replacement.user_agent == "pytest-refresh"


@pytest.mark.asyncio
async def test_refresh_rejects_expired_token(
    db_session: AsyncSession, registered_auth
) -> None:
    session_id = decode_access_token(registered_auth.access_token.token).session_id
    record = await db_session.get(AuthSession, session_id)
    assert record is not None
    record.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db_session.flush()

    with pytest.raises(InvalidRefreshToken):
        await rotate_refresh_token(db_session, registered_auth.refresh_token, "pytest-refresh")

    assert record.revoked_at is None


@pytest.mark.asyncio
async def test_refresh_rejects_inactive_user(
    db_session: AsyncSession, registered_auth
) -> None:
    registered_auth.user.is_active = False
    await db_session.flush()

    with pytest.raises(InvalidRefreshToken):
        await rotate_refresh_token(db_session, registered_auth.refresh_token, "pytest-refresh")

    sessions = (await db_session.scalars(select(AuthSession))).all()
    assert len(sessions) == 1


@pytest.mark.asyncio
async def test_refresh_replay_revokes_entire_session_family(
    db_session: AsyncSession, registered_auth
) -> None:
    await rotate_refresh_token(db_session, registered_auth.refresh_token, "pytest-refresh")
    old_session_id = decode_access_token(registered_auth.access_token.token).session_id
    old_record = await db_session.get(AuthSession, old_session_id)
    assert old_record is not None

    with pytest.raises(InvalidRefreshToken):
        await rotate_refresh_token(db_session, registered_auth.refresh_token, "pytest-replay")

    family_sessions = (
        await db_session.scalars(
            select(AuthSession).where(AuthSession.family_id == old_record.family_id)
        )
    ).all()
    assert len(family_sessions) == 2
    assert all(auth_session.revoked_at is not None for auth_session in family_sessions)


@pytest.mark.asyncio
async def test_revoke_session_family_only_revokes_matching_family(
    db_session: AsyncSession, registered_auth
) -> None:
    await rotate_refresh_token(db_session, registered_auth.refresh_token, "pytest-refresh")
    separate_auth = await authenticate_user(
        db_session,
        LoginRequest(email="student@example.com", password="learning2026"),
        "pytest-login",
    )
    first_session_id = decode_access_token(registered_auth.access_token.token).session_id
    first_record = await db_session.get(AuthSession, first_session_id)
    separate_session_id = decode_access_token(separate_auth.access_token.token).session_id
    separate_record = await db_session.get(AuthSession, separate_session_id)
    assert first_record is not None
    assert separate_record is not None

    await revoke_session_family(db_session, first_record.family_id)

    family_sessions = (
        await db_session.scalars(
            select(AuthSession).where(AuthSession.family_id == first_record.family_id)
        )
    ).all()
    assert all(auth_session.revoked_at is not None for auth_session in family_sessions)
    assert separate_record.revoked_at is None


@pytest.mark.asyncio
async def test_logout_is_idempotent(db_session: AsyncSession, registered_auth) -> None:
    await revoke_refresh_token(db_session, registered_auth.refresh_token)
    await revoke_refresh_token(db_session, registered_auth.refresh_token)

    session_id = decode_access_token(registered_auth.access_token.token).session_id
    record = await db_session.get(AuthSession, session_id)
    assert record is not None
    assert record.revoked_at is not None


@pytest.mark.asyncio
async def test_logout_ignores_unknown_refresh_token(db_session: AsyncSession) -> None:
    await revoke_refresh_token(db_session, "unknown-refresh-token")


@pytest.mark.asyncio
async def test_logout_all_only_revokes_selected_users_sessions(
    db_session: AsyncSession, registered_auth
) -> None:
    selected_user = registered_auth.user
    selected_login = await authenticate_user(
        db_session,
        LoginRequest(email="student@example.com", password="learning2026"),
        "pytest-login",
    )
    other_auth = await register_user(
        db_session,
        RegisterRequest(
            email="other@example.com",
            nickname="Other",
            password="learning2026",
        ),
        "pytest-other",
    )

    await revoke_all_user_sessions(db_session, selected_user.id)

    selected_session_ids = {
        decode_access_token(registered_auth.access_token.token).session_id,
        decode_access_token(selected_login.access_token.token).session_id,
    }
    selected_sessions = [
        await db_session.get(AuthSession, session_id)
        for session_id in selected_session_ids
    ]
    other_session = await db_session.get(
        AuthSession,
        decode_access_token(other_auth.access_token.token).session_id,
    )

    assert all(auth_session is not None and auth_session.revoked_at is not None for auth_session in selected_sessions)
    assert other_session is not None
    assert other_session.revoked_at is None
