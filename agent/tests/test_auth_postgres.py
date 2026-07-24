"""PostgreSQL integration coverage for authentication and ownership races."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from api.projects import create_project
from db.models import AuthSession, Project, SourceMaterial, User
from schema.auth import RegisterRequest
from schema.project import ProjectCreateRequest
from services.auth_service import (
    AuthResult,
    EmailAlreadyRegistered,
    InvalidRefreshToken,
    register_user,
    revoke_all_user_sessions,
    rotate_refresh_token,
)


pytestmark = pytest.mark.postgres


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.fail("DATABASE_URL is required for PostgreSQL integration tests")
    return url


class _StartGate:
    """Hold cooperating tasks until every participant reaches the named boundary."""

    def __init__(self, participants: int) -> None:
        self.participants = participants
        self.arrivals = 0
        self._released = asyncio.Event()

    async def wait(self) -> None:
        self.arrivals += 1
        if self.arrivals == self.participants:
            self._released.set()
        await asyncio.wait_for(self._released.wait(), timeout=5)


class _GateFirstScalarSession:
    """Gate workers after their first scalar read and before its mutation follows."""

    def __init__(self, session: AsyncSession, gate: _StartGate) -> None:
        self._session = session
        self._gate = gate
        self._gated = False

    async def scalar(self, *args, **kwargs):
        result = await self._session.scalar(*args, **kwargs)
        if not self._gated:
            self._gated = True
            await self._gate.wait()
        return result

    def __getattr__(self, name: str):
        return getattr(self._session, name)


class _GateFirstExecuteSession:
    """Gate a session immediately before its first execute operation."""

    def __init__(self, session: AsyncSession, gate: _StartGate) -> None:
        self._session = session
        self._gate = gate
        self._gated = False

    async def execute(self, *args, **kwargs):
        if not self._gated:
            self._gated = True
            await self._gate.wait()
        return await self._session.execute(*args, **kwargs)

    def __getattr__(self, name: str):
        return getattr(self._session, name)


@pytest_asyncio.fixture
async def postgres_engine():
    """Use a per-test event loop and connections with no cross-test pooling."""
    engine = create_async_engine(
        _database_url(),
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
def postgres_sessions(postgres_engine):
    return async_sessionmaker(postgres_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def clean_postgres(postgres_engine):
    """Keep each live-service case independent without changing application code."""
    async with postgres_engine.begin() as connection:
        await connection.execute(
            text("TRUNCATE TABLE users, projects, source_materials RESTART IDENTITY CASCADE")
        )
    yield


async def _register(session_factory, email: str = "student@example.com") -> AuthResult:
    async with session_factory() as session:
        result = await register_user(
            session,
            RegisterRequest(
                email=email,
                nickname="Student",
                password="learning2026",
            ),
            "postgres-seed",
        )
        await session.commit()
        return result


def _run_alembic(*arguments: str) -> None:
    """Run a real migration command against the test service."""
    agent_dir = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=agent_dir,
        env=os.environ.copy(),
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


@pytest.mark.asyncio
async def test_live_migration_roundtrip_preserves_representable_data_and_drops_owner_only_materials(
    postgres_engine,
) -> None:
    """Exercise upgrade/downgrade data policy on pgvector rather than SQL text alone."""
    legacy_project_id = uuid.uuid4()
    legacy_material_id = uuid.uuid4()
    owner_only_material_id = uuid.uuid4()
    owned_project_id = uuid.uuid4()
    owned_material_id = uuid.uuid4()
    owner_id = uuid.uuid4()

    _run_alembic("downgrade", "20260724_0001")
    async with postgres_engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO projects (id, title, audience, difficulty, status, owner_id) "
                "VALUES (:id, 'Legacy project', 'undergraduate_cs', 'intermediate', 'draft', 'legacy-owner')"
            ),
            {"id": legacy_project_id},
        )
        await connection.execute(
            text("INSERT INTO source_materials (id, project_id, type) VALUES (:id, :project_id, 'text')"),
            {"id": legacy_material_id, "project_id": legacy_project_id},
        )

    _run_alembic("upgrade", "head")
    async with postgres_engine.begin() as connection:
        assert (
            await connection.scalar(
                text("SELECT owner_id FROM projects WHERE id = :id"), {"id": legacy_project_id}
            )
        ) is None
        assert (
            await connection.scalar(
                text("SELECT owner_id FROM source_materials WHERE id = :id"),
                {"id": legacy_material_id},
            )
        ) is None
        await connection.execute(
            text(
                "INSERT INTO users (id, email, email_normalized, nickname, password_hash) "
                "VALUES (:id, 'owner@example.com', 'owner@example.com', 'Owner', 'not-used')"
            ),
            {"id": owner_id},
        )
        await connection.execute(
            text(
                "INSERT INTO source_materials (id, project_id, owner_id, type) "
                "VALUES (:id, NULL, :owner_id, 'text')"
            ),
            {"id": owner_only_material_id, "owner_id": owner_id},
        )
        await connection.execute(
            text(
                "INSERT INTO projects (id, title, audience, difficulty, status, owner_id) "
                "VALUES (:id, 'Owned project', 'undergraduate_cs', 'intermediate', 'draft', :owner_id)"
            ),
            {"id": owned_project_id, "owner_id": owner_id},
        )
        await connection.execute(
            text(
                "INSERT INTO source_materials (id, project_id, owner_id, type) "
                "VALUES (:id, :project_id, :owner_id, 'text')"
            ),
            {
                "id": owned_material_id,
                "project_id": owned_project_id,
                "owner_id": owner_id,
            },
        )

    _run_alembic("downgrade", "20260724_0001")
    async with postgres_engine.connect() as connection:
        assert await connection.scalar(
            text("SELECT count(*) FROM source_materials WHERE id = :id"),
            {"id": owner_only_material_id},
        ) == 0
        assert await connection.scalar(
            text("SELECT count(*) FROM source_materials WHERE id = :id"),
            {"id": legacy_material_id},
        ) == 1
        assert await connection.scalar(
            text("SELECT count(*) FROM projects WHERE id = :id"),
            {"id": owned_project_id},
        ) == 1
        assert await connection.scalar(
            text("SELECT count(*) FROM source_materials WHERE id = :id"),
            {"id": owned_material_id},
        ) == 1

    _run_alembic("upgrade", "head")
    async with postgres_engine.connect() as connection:
        assert await connection.scalar(
            text("SELECT owner_id FROM projects WHERE id = :id"),
            {"id": owned_project_id},
        ) is None
        assert await connection.scalar(
            text("SELECT project_id FROM source_materials WHERE id = :id"),
            {"id": owned_material_id},
        ) == owned_project_id
        assert await connection.scalar(
            text("SELECT owner_id FROM source_materials WHERE id = :id"),
            {"id": owned_material_id},
        ) is None
        assert await connection.scalar(
            text("SELECT count(*) FROM users WHERE id = :id"), {"id": owner_id}
        ) == 0


@pytest.mark.asyncio
async def test_concurrent_registration_allows_one_normalized_email(postgres_sessions) -> None:
    """The unique constraint resolves concurrent normalized-email registration."""
    gate = _StartGate(2)

    async def attempt(email: str):
        async with postgres_sessions() as session:
            try:
                result = await register_user(
                    _GateFirstScalarSession(session, gate),
                    RegisterRequest(email=email, nickname="Student", password="learning2026"),
                    "postgres-registration",
                )
                await session.commit()
                return result
            except EmailAlreadyRegistered as error:
                await session.rollback()
                return error

    results = await asyncio.gather(
        attempt("Student@Example.com"),
        attempt("student@example.com"),
    )

    assert gate.arrivals == 2
    assert sum(isinstance(item, AuthResult) for item in results) == 1
    assert sum(isinstance(item, EmailAlreadyRegistered) for item in results) == 1
    async with postgres_sessions() as session:
        assert len(list(await session.scalars(select(User)))) == 1


@pytest.mark.asyncio
async def test_concurrent_same_token_refresh_has_one_winner(postgres_sessions, monkeypatch) -> None:
    """Row locks permit one rotation and reject the same-token concurrent replay."""
    registered = await _register(postgres_sessions)

    gate = _StartGate(2)
    from services import auth_service

    original_lock_user = auth_service._lock_user

    async def gated_lock_user(session, user_id):
        await gate.wait()
        return await original_lock_user(session, user_id)

    monkeypatch.setattr(auth_service, "_lock_user", gated_lock_user)

    async def rotate(user_agent: str):
        async with postgres_sessions() as session:
            try:
                result = await rotate_refresh_token(session, registered.refresh_token, user_agent)
                await session.commit()
                return result
            except InvalidRefreshToken as error:
                await session.rollback()
                return error

    results = await asyncio.gather(
        rotate("postgres-test-a"),
        rotate("postgres-test-b"),
    )

    assert gate.arrivals == 2
    assert sum(isinstance(item, AuthResult) for item in results) == 1
    assert sum(isinstance(item, InvalidRefreshToken) for item in results) == 1


@pytest.mark.asyncio
async def test_replay_racing_with_replacement_rotation_revokes_the_family(
    postgres_sessions, monkeypatch
) -> None:
    """A replay cannot leave a concurrently rotated descendant usable."""
    registered = await _register(postgres_sessions)
    async with postgres_sessions() as session:
        replacement = await rotate_refresh_token(session, registered.refresh_token, "first-rotation")
        await session.commit()

    gate = _StartGate(2)
    from services import auth_service

    original_lock_user = auth_service._lock_user
    lock_calls = 0

    async def gated_lock_user(session, user_id):
        nonlocal lock_calls
        lock_calls += 1
        if lock_calls <= 2:
            await gate.wait()
        return await original_lock_user(session, user_id)

    monkeypatch.setattr(auth_service, "_lock_user", gated_lock_user)

    async def rotate(token: str):
        async with postgres_sessions() as session:
            try:
                result = await rotate_refresh_token(session, token, "postgres-race")
                await session.commit()
                return result
            except InvalidRefreshToken as error:
                await session.rollback()
                return error

    results = await asyncio.gather(
        rotate(registered.refresh_token),
        rotate(replacement.refresh_token),
    )

    assert gate.arrivals == 2
    assert any(isinstance(item, InvalidRefreshToken) for item in results)
    async with postgres_sessions() as session:
        records = list(await session.scalars(select(AuthSession)))
    assert records
    assert all(record.revoked_at is not None for record in records)


@pytest.mark.asyncio
async def test_logout_all_racing_with_rotation_leaves_no_active_sessions(
    postgres_sessions, monkeypatch
) -> None:
    """Logout-all serializes with rotation and wins regardless of scheduling order."""
    registered = await _register(postgres_sessions)

    gate = _StartGate(2)
    from services import auth_service

    original_lock_user = auth_service._lock_user

    async def gated_lock_user(session, user_id):
        await gate.wait()
        return await original_lock_user(session, user_id)

    monkeypatch.setattr(auth_service, "_lock_user", gated_lock_user)

    async def logout_all() -> None:
        async with postgres_sessions() as session:
            await revoke_all_user_sessions(session, registered.user.id)
            await session.commit()

    async def rotate():
        async with postgres_sessions() as session:
            try:
                result = await rotate_refresh_token(session, registered.refresh_token, "postgres-race")
                await session.commit()
                return result
            except InvalidRefreshToken as error:
                await session.rollback()
                return error

    logout_result, rotation_result = await asyncio.gather(logout_all(), rotate())

    assert gate.arrivals == 2
    assert logout_result is None
    assert isinstance(rotation_result, (AuthResult, InvalidRefreshToken))
    async with postgres_sessions() as session:
        active_sessions = list(
            await session.scalars(select(AuthSession).where(AuthSession.revoked_at.is_(None)))
        )
    assert active_sessions == []


@pytest.mark.asyncio
async def test_concurrent_project_binding_claims_an_unbound_material_once(postgres_sessions) -> None:
    """FOR UPDATE prevents two projects from claiming the same owner material."""
    registered = await _register(postgres_sessions, "material-owner@example.com")
    material_id = uuid.uuid4()
    async with postgres_sessions() as session:
        session.add(SourceMaterial(id=material_id, owner_id=registered.user.id, type="text"))
        await session.commit()

    gate = _StartGate(2)

    async def create(title: str):
        async with postgres_sessions() as session:
            try:
                result = await create_project(
                    ProjectCreateRequest(
                        title=title,
                        constraints={"material_ids": [str(material_id)]},
                    ),
                    SimpleNamespace(id=registered.user.id),
                    _GateFirstExecuteSession(session, gate),
                )
                await session.commit()
                return result
            except HTTPException as error:
                await session.rollback()
                return error

    results = await asyncio.gather(create("First claim"), create("Second claim"))

    assert gate.arrivals == 2
    assert sum(isinstance(item, dict) for item in results) == 1
    assert sum(isinstance(item, HTTPException) and item.status_code == 400 for item in results) == 1
    async with postgres_sessions() as session:
        material = await session.get(SourceMaterial, material_id)
        projects = list(await session.scalars(select(Project)))
    assert material is not None
    assert material.project_id is not None
    assert len(projects) == 1
    assert projects[0].id == material.project_id
