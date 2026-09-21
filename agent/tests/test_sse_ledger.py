"""Durable SSE event replay and ownership tests."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from db.models import Project, SSEEvent, SSEStream, UsageLedger, User
from tests.test_db_integration import _make_sqlite_compatible

_make_sqlite_compatible()


@pytest.mark.asyncio
async def test_stream_is_registered_before_client_connects(test_db):
    from services.sse_ledger import register_sse_stream

    project_id = uuid.uuid4()
    stream_id = uuid.uuid4()
    test_db.add(Project(id=project_id, title="Pre-registered stream"))
    await test_db.flush()

    await register_sse_stream(
        test_db,
        stream_id=str(stream_id),
        project_id=str(project_id),
        kind="generation",
    )

    stream = await test_db.get(SSEStream, stream_id)
    assert stream is not None
    assert stream.project_id == project_id
    assert stream.status == "active"
    assert stream.last_event_id == 0


@pytest.mark.asyncio
async def test_start_generation_returns_a_persisted_stream(test_db):
    from api.generate import start_generation
    from schema.project import GenerateRequest

    project_id = uuid.uuid4()
    project = Project(id=project_id, title="Atomic generation start")
    test_db.add(project)
    await test_db.flush()

    result = await start_generation(
        str(project_id),
        GenerateRequest(action="modules", modules=["quiz"]),
        test_db,
        None,
        None,
    )

    stream_id = uuid.UUID(result["stream_url"].split("stream_id=", 1)[1])
    stream = await test_db.get(SSEStream, stream_id)
    assert stream is not None
    assert stream.project_id == project_id
    assert project.status == "planning"


@pytest.mark.asyncio
async def test_cancel_generation_retires_stream_and_releases_project_lock(test_db):
    from api.generate import cancel_generation
    from services.quota import reserve_quota

    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    stream_id = uuid.uuid4()
    quota_key = "cancel-active-generation"
    user = User(
        id=user_id,
        email="cancel-generation@example.com",
        nickname="Cancel generation",
        password_hash="test",
    )
    project = Project(
        id=project_id,
        title="Abandoned generation",
        owner_id=str(user_id),
        status="generating",
        dsl_snapshot={
            "input_content": "BFS",
            "_pending_action": "modules",
            "_pending_modules": ["video"],
            "_quota_ref": {
                "resource": "generation",
                "idempotency_key": quota_key,
                "stream_id": str(stream_id),
            },
        },
    )
    stream = SSEStream(
        id=stream_id,
        project_id=project_id,
        kind="generation",
        status="active",
        producer_id="producer",
        lease_expires_at=datetime.now(UTC) + timedelta(minutes=1),
    )
    test_db.add_all([user, project, stream])
    await test_db.flush()
    await reserve_quota(
        test_db,
        user_id=user_id,
        resource="generation",
        idempotency_key=quota_key,
        details={"project_id": str(project_id), "stream_id": str(stream_id)},
    )

    result = await cancel_generation(str(project_id), test_db, SimpleNamespace(id=user_id))

    assert result == {"project_id": str(project_id), "status": "cancelled"}
    assert project.status == "draft"
    assert project.dsl_snapshot == {"input_content": "BFS"}
    assert stream.status == "completed"
    assert stream.completed_at is not None
    assert stream.producer_id is None
    ledger = list((await test_db.scalars(select(UsageLedger).where(
        UsageLedger.user_id == user_id,
        UsageLedger.resource == "generation",
    ))).all())
    assert any(
        isinstance(row.details, dict)
        and row.details.get("_quota_state") == "settled"
        and row.details.get("_quota_reservation") == quota_key
        for row in ledger
    )
    assert await cancel_generation(
        str(project_id), test_db, SimpleNamespace(id=user_id)
    ) == {"project_id": str(project_id), "status": "cancelled"}


@pytest.mark.asyncio
async def test_missing_unstarted_stream_releases_quota_and_restores_project(test_db):
    from api.generate import _recover_or_resume_generation
    from services.quota import reserve_quota

    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    stream_id = uuid.uuid4()
    quota_key = "generation-that-never-connected"
    test_db.add(
        User(
            id=user_id,
            email="stale-stream@example.com",
            nickname="Stale stream",
            password_hash="test",
        )
    )
    project = Project(
        id=project_id,
        title="Stale generation",
        owner_id=str(user_id),
        status="planning",
        dsl_snapshot={
            "_pending_action": "modules",
            "_quota_ref": {
                "resource": "generation",
                "idempotency_key": quota_key,
                "stream_id": str(stream_id),
            },
        },
    )
    test_db.add(project)
    await test_db.flush()
    await reserve_quota(
        test_db,
        user_id=user_id,
        resource="generation",
        idempotency_key=quota_key,
        details={"project_id": str(project_id), "stream_id": str(stream_id)},
    )

    result = await _recover_or_resume_generation(
        test_db,
        SimpleNamespace(id=user_id),
        project,
        project_id=str(project_id),
    )

    assert result is None
    assert project.status == "draft"
    assert "_quota_ref" not in project.dsl_snapshot
    ledger = list(
        (
            await test_db.scalars(
                select(UsageLedger).where(UsageLedger.user_id == user_id)
            )
        ).all()
    )
    assert any(
        isinstance(row.details, dict)
        and row.details.get("_quota_state") == "released"
        and row.details.get("_quota_reservation") == quota_key
        for row in ledger
    )


@pytest.mark.asyncio
async def test_events_are_committed_before_replay_and_terminal_does_not_rerun(test_db):
    from services.sse_ledger import durable_sse_stream

    project_id = uuid.uuid4()
    stream_id = uuid.uuid4()
    test_db.add(Project(id=project_id, title="SSE ledger"))
    await test_db.commit()
    factory = async_sessionmaker(test_db.bind, expire_on_commit=False)

    async def source():
        yield {"event": "progress", "data": json.dumps({"phase": "planner", "pct": 10})}
        yield {"event": "done", "data": json.dumps({"phase": "done", "pct": 100})}

    with patch("db.database.async_session_factory", factory):
        first = [
            event
            async for event in durable_sse_stream(
                source(),
                stream_id=str(stream_id),
                project_id=str(project_id),
                kind="generation",
            )
        ]

        reran = False

        async def must_not_run():
            nonlocal reran
            reran = True
            yield {"event": "error", "data": "{}"}

        replay = [
            event
            async for event in durable_sse_stream(
                must_not_run(),
                stream_id=str(stream_id),
                project_id=str(project_id),
                kind="generation",
                last_event_id=1,
            )
        ]

    assert [event["id"] for event in first] == ["1", "2"]
    assert [event["id"] for event in replay] == ["2"]
    assert reran is False
    stream = await test_db.get(SSEStream, stream_id)
    rows = (
        await test_db.scalars(select(SSEEvent).where(SSEEvent.stream_id == stream_id))
    ).all()
    assert stream.status == "completed"
    assert stream.last_event_id == 2
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_stream_id_cannot_be_reused_for_another_project(test_db):
    from services.sse_ledger import durable_sse_stream

    first_project, second_project, stream_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    test_db.add_all(
        [
            Project(id=first_project, title="First"),
            Project(id=second_project, title="Second"),
            SSEStream(
                id=stream_id,
                project_id=first_project,
                kind="generation",
                status="active",
            ),
        ]
    )
    await test_db.commit()
    factory = async_sessionmaker(test_db.bind, expire_on_commit=False)

    async def source():
        yield {"event": "done", "data": "{}"}

    with patch("db.database.async_session_factory", factory), pytest.raises(PermissionError):
        _ = [
            event
            async for event in durable_sse_stream(
                source(),
                stream_id=str(stream_id),
                project_id=str(second_project),
                kind="generation",
            )
        ]


@pytest.mark.asyncio
async def test_active_stream_discovery_returns_latest_safe_replay_url(test_db):
    from api.generate import get_active_stream

    project_id = uuid.uuid4()
    older_id, latest_id = uuid.uuid4(), uuid.uuid4()
    now = datetime.now(UTC)
    test_db.add(Project(id=project_id, title="Discover stream"))
    test_db.add_all(
        [
            SSEStream(
                id=older_id,
                project_id=project_id,
                kind="generation",
                status="active",
                last_event_id=3,
                created_at=now - timedelta(minutes=1),
            ),
            SSEStream(
                id=latest_id,
                project_id=project_id,
                kind="modules",
                status="active",
                last_event_id=7,
                created_at=now,
            ),
        ]
    )
    await test_db.commit()

    result = await get_active_stream(str(project_id), test_db)

    assert result["stream_id"] == str(latest_id)
    assert result["kind"] == "modules"
    assert result["last_event_id"] == 7
    assert result["stream_url"].startswith(
        f"/api/projects/{project_id}/generate/modules/stream"
    )
    assert "stream_id=" in result["stream_url"]


def test_active_stream_url_refuses_resume_feedback_and_unsafe_module_ids():
    from api.generate import _active_stream_url

    assert _active_stream_url("p1", "s1", "resume") is None
    assert _active_stream_url("p1", "s1", "module:../../secret") is None
