"""Admin user/role/session management invariants."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.admin import (
    AdminUserUpdate,
    list_users,
    revoke_user_sessions,
    update_user,
)
from db.models import AuditEvent, AuthSession, User
from scripts.bootstrap_admin import bootstrap_admin
from services.auth_service import hash_password, hash_session_token


@pytest_asyncio.fixture
async def admin_db():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(User.__table__.create)
        await connection.run_sync(AuthSession.__table__.create)
        await connection.run_sync(AuditEvent.__table__.create)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _user(test_db, email: str, role: str = "teacher", active: bool = True) -> User:
    user = User(
        id=uuid.uuid4(),
        email=email,
        nickname=email.split("@")[0],
        password_hash=hash_password("secure-password-42"),
        role=role,
        is_active=active,
    )
    test_db.add(user)
    await test_db.flush()
    return user


async def _session(test_db, user: User, token: str, *, expired: bool = False) -> None:
    test_db.add(
        AuthSession(
            id=uuid.uuid4(),
            user_id=user.id,
            token_hash=hash_session_token(token),
            expires_at=datetime.now(timezone.utc)
            + (timedelta(days=-1) if expired else timedelta(days=1)),
        )
    )
    await test_db.flush()


@pytest.mark.asyncio
async def test_admin_lists_filtered_users_with_opaque_cursor_and_active_sessions(admin_db):
    admin = await _user(admin_db, "admin@example.com", "admin")
    teacher = await _user(admin_db, "teacher@example.com")
    await _user(admin_db, "inactive@example.com", active=False)
    await _session(admin_db, teacher, "live")
    await _session(admin_db, teacher, "expired", expired=True)

    first = await list_users(admin_db, admin, None, None, None, None, 2)
    assert len(first["users"]) == 2
    assert first["next_cursor"] is not None
    assert "password_hash" not in first["users"][0]

    second = await list_users(
        admin_db, admin, uuid.UUID(first["next_cursor"]), None, None, None, 2
    )
    assert {row["id"] for row in first["users"]}.isdisjoint(
        row["id"] for row in second["users"]
    ), (first, second)
    filtered = await list_users(admin_db, admin, None, "teacher", True, "teacher", 50)
    assert [row["email"] for row in filtered["users"]] == ["teacher@example.com"]
    assert filtered["users"][0]["session_count"] == 1


@pytest.mark.asyncio
async def test_role_change_revokes_sessions_and_writes_audit(admin_db):
    admin = await _user(admin_db, "admin@example.com", "admin")
    target = await _user(admin_db, "target@example.com")
    await _session(admin_db, target, "one")

    result = await update_user(
        target.id, AdminUserUpdate(role="student"), admin_db, admin
    )

    assert result["role"] == "student"
    assert result["session_count"] == 0
    assert await admin_db.scalar(
        select(AuthSession).where(AuthSession.user_id == target.id)
    ) is None
    event = await admin_db.scalar(
        select(AuditEvent).where(AuditEvent.action == "admin.user.update")
    )
    assert event is not None
    assert event.actor_id == admin.id
    assert event.details["before"]["role"] == "teacher"
    assert event.details["after"]["role"] == "student"
    assert event.details["sessions_revoked"] == 1


@pytest.mark.asyncio
async def test_admin_cannot_remove_own_access(admin_db):
    admin = await _user(admin_db, "admin@example.com", "admin")
    await _user(admin_db, "backup@example.com", "admin")

    with pytest.raises(HTTPException) as caught:
        await update_user(
            admin.id, AdminUserUpdate(is_active=False), admin_db, admin
        )
    assert caught.value.status_code == 409


@pytest.mark.asyncio
async def test_last_active_admin_cannot_be_removed(admin_db):
    admin = await _user(admin_db, "admin@example.com", "admin")
    target = await _user(admin_db, "last@example.com", "admin")
    admin.role = "teacher"
    await admin_db.flush()

    with pytest.raises(HTTPException) as caught:
        await update_user(
            target.id, AdminUserUpdate(role="teacher"), admin_db, admin
        )
    assert caught.value.status_code == 409
    assert target.role == "admin"


@pytest.mark.asyncio
async def test_admin_revokes_all_target_sessions_and_audits(admin_db):
    admin = await _user(admin_db, "admin@example.com", "admin")
    target = await _user(admin_db, "target@example.com")
    await _session(admin_db, target, "one")
    await _session(admin_db, target, "two")

    assert await revoke_user_sessions(target.id, admin_db, admin) == {"revoked": 2}
    assert await admin_db.scalar(
        select(AuthSession).where(AuthSession.user_id == target.id)
    ) is None
    event = await admin_db.scalar(
        select(AuditEvent).where(AuditEvent.action == "admin.sessions.revoke")
    )
    assert event is not None
    assert event.details == {"sessions_revoked": 2}


@pytest.mark.asyncio
async def test_invalid_user_cursor_and_unknown_target_are_public_errors(admin_db):
    admin = await _user(admin_db, "admin@example.com", "admin")
    missing = uuid.uuid4()

    with pytest.raises(HTTPException) as cursor_error:
        await list_users(admin_db, admin, missing, None, None, None, 50)
    assert cursor_error.value.status_code == 422

    with pytest.raises(HTTPException) as target_error:
        await revoke_user_sessions(missing, admin_db, admin)
    assert target_error.value.status_code == 404


@pytest.mark.asyncio
async def test_bootstrap_admin_is_audited_idempotent_and_closes_after_first_admin(admin_db):
    first = await _user(admin_db, "first@example.com", active=False)
    second = await _user(admin_db, "second@example.com")
    await _session(admin_db, first, "old-session")

    result = await bootstrap_admin(admin_db, " FIRST@example.com ")
    assert result["changed"] is True
    assert first.role == "admin"
    assert first.is_active is True
    assert await admin_db.scalar(
        select(AuthSession).where(AuthSession.user_id == first.id)
    ) is None
    event = await admin_db.scalar(
        select(AuditEvent).where(AuditEvent.action == "admin.bootstrap")
    )
    assert event is not None

    assert (await bootstrap_admin(admin_db, first.email))["changed"] is False
    with pytest.raises(RuntimeError, match="already exists"):
        await bootstrap_admin(admin_db, second.email)
