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


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def postgres_engine():
    """Connect directly to the PostgreSQL service prepared by Alembic."""
    engine = create_async_engine(_database_url(), pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def postgres_sessions(postgres_engine):
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

    _run_alembic("upgrade", "head")


@pytest.mark.asyncio
async def test_concurrent_registration_allows_one_normalized_email(postgres_sessions) -> None:
    """The unique constraint resolves concurrent normalized-email registration."""
    async def attempt(email: str):
        async with postgres_sessions() as session:
            try:
                result = await register_user(
                    session,
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

    assert sum(isinstance(item, AuthResult) for item in results) == 1
    assert sum(isinstance(item, EmailAlreadyRegistered) for item in results) == 1
    async with postgres_sessions() as session:
        assert len(list(await session.scalars(select(User)))) == 1


@pytest.mark.asyncio
async def test_concurrent_same_token_refresh_has_one_winner(postgres_sessions) -> None:
    """Row locks permit one rotation and reject the same-token concurrent replay."""
    registered = await _register(postgres_sessions)

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

    assert sum(isinstance(item, AuthResult) for item in results) == 1
    assert sum(isinstance(item, InvalidRefreshToken) for item in results) == 1


@pytest.mark.asyncio
async def test_replay_racing_with_replacement_rotation_revokes_the_family(postgres_sessions) -> None:
    """A replay cannot leave a concurrently rotated descendant usable."""
    registered = await _register(postgres_sessions)
    async with postgres_sessions() as session:
        replacement = await rotate_refresh_token(session, registered.refresh_token, "first-rotation")
        await session.commit()

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

    assert any(isinstance(item, InvalidRefreshToken) for item in results)
    async with postgres_sessions() as session:
        records = list(await session.scalars(select(AuthSession)))
    assert records
    assert all(record.revoked_at is not None for record in records)


@pytest.mark.asyncio
async def test_logout_all_racing_with_rotation_leaves_no_active_sessions(postgres_sessions) -> None:
    """Logout-all serializes with rotation and wins regardless of scheduling order."""
    registered = await _register(postgres_sessions)

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

    async def create(title: str):
        async with postgres_sessions() as session:
            try:
                result = await create_project(
                    ProjectCreateRequest(
                        title=title,
                        constraints={"material_ids": [str(material_id)]},
                    ),
                    SimpleNamespace(id=registered.user.id),
                    session,
                )
                await session.commit()
                return result
            except HTTPException as error:
                await session.rollback()
                return error

    results = await asyncio.gather(create("First claim"), create("Second claim"))

    assert sum(isinstance(item, dict) for item in results) == 1
    assert sum(isinstance(item, HTTPException) and item.status_code == 400 for item in results) == 1
    async with postgres_sessions() as session:
        material = await session.get(SourceMaterial, material_id)
        projects = list(await session.scalars(select(Project)))
    assert material is not None
    assert material.project_id is not None
    assert len(projects) == 1
    assert projects[0].id == material.project_id
