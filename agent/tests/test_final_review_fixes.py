"""Regression coverage for the final backend security review findings."""

from __future__ import annotations

import logging
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from starlette.requests import Request


class _TrackingSessionContext:
    """Wrap one real test session and record when its context has closed."""

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory
        self._session = None
        self.closed = False

    async def __aenter__(self):
        self._session = self._session_factory()
        return await self._session.__aenter__()

    async def __aexit__(self, exc_type, exc, traceback) -> bool:
        assert self._session is not None
        try:
            return await self._session.__aexit__(exc_type, exc, traceback)
        finally:
            self.closed = True


class _TrackingSessionFactory:
    """Provide independently closed short-lived sessions to stream helpers."""

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory
        self.contexts: list[_TrackingSessionContext] = []

    def __call__(self) -> _TrackingSessionContext:
        context = _TrackingSessionContext(self._session_factory)
        self.contexts.append(context)
        return context


def _use_tracking_stream_sessions(monkeypatch, session_factory) -> _TrackingSessionFactory:
    """Send both stream authorization phases through observable SQLite sessions."""
    from api import deps, generate

    factory = _TrackingSessionFactory(session_factory)
    monkeypatch.setattr(deps, "async_session_factory", factory, raising=False)
    monkeypatch.setattr(generate, "async_session_factory", factory, raising=False)
    return factory


async def _register_user(auth_api_client, email: str) -> dict[str, object]:
    response = await auth_api_client.client.post(
        "/api/auth/register",
        json={
            "email": email,
            "nickname": email.split("@", maxsplit=1)[0],
            "password": "learning2026",
        },
    )
    assert response.status_code == 201
    return {
        "id": UUID(response.json()["user"]["id"]),
        "headers": {"Authorization": f"Bearer {response.json()['access_token']}"},
    }


async def _create_project(
    auth_api_client,
    owner_id: UUID,
    title: str,
    constraints: dict[str, object] | None = None,
):
    from db.models import Project

    project = Project(
        id=uuid4(),
        owner_id=owner_id,
        title=title,
        audience="undergraduate_cs",
        difficulty="intermediate",
        status="draft",
        dsl_snapshot={"constraints": constraints or {}},
    )
    async with auth_api_client.session_factory() as session:
        session.add(project)
        await session.commit()
    return project


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("stream_path", "service_name"),
    [
        ("generate/stream", "run_generation_stream"),
        ("generate/resume/stream", "resume_generation_stream"),
        ("generate/regenerate/stream", "run_regenerate_stream"),
    ],
)
async def test_sse_sessions_close_before_the_stream_service_starts(
    auth_api_client,
    monkeypatch: pytest.MonkeyPatch,
    stream_path: str,
    service_name: str,
) -> None:
    """Bearer lookup and project ownership must release DB sessions before SSE runs."""
    from api import generate

    user = await _register_user(auth_api_client, "sse-owner@example.com")
    project = await _create_project(auth_api_client, user["id"], "SSE owner project")
    tracked_sessions = _use_tracking_stream_sessions(
        monkeypatch, auth_api_client.session_factory
    )
    service_started_after_closure: list[bool] = []

    async def short_stream(*_args, **_kwargs):
        service_started_after_closure.append(
            len(tracked_sessions.contexts) == 2
            and all(context.closed for context in tracked_sessions.contexts)
        )
        yield {"data": "complete"}

    monkeypatch.setattr(generate, service_name, short_stream)

    response = await auth_api_client.client.get(
        f"/api/projects/{project.id}/{stream_path}", headers=user["headers"]
    )

    assert response.status_code == 200
    assert len(tracked_sessions.contexts) == 2
    assert all(context.closed for context in tracked_sessions.contexts)
    assert service_started_after_closure == [True]


@pytest.mark.asyncio
async def test_sse_authorizes_before_starting_the_generation_service(
    auth_api_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A foreign project is rejected before the stream service can observe it."""
    from api import generate

    user_a = await _register_user(auth_api_client, "sse-owner-a@example.com")
    user_b = await _register_user(auth_api_client, "sse-owner-b@example.com")
    project_owned_by_user_b = await _create_project(
        auth_api_client, user_b["id"], "SSE foreign project"
    )
    tracked_sessions = _use_tracking_stream_sessions(
        monkeypatch, auth_api_client.session_factory
    )
    service_calls: list[bool] = []

    async def unexpected_stream(*_args, **_kwargs):
        service_calls.append(True)
        if False:
            yield {"data": "unreachable"}

    monkeypatch.setattr(generate, "run_generation_stream", unexpected_stream)

    response = await auth_api_client.client.get(
        f"/api/projects/{project_owned_by_user_b.id}/generate/stream",
        headers=user_a["headers"],
    )

    assert response.status_code == 404
    assert service_calls == []
    assert len(tracked_sessions.contexts) == 2
    assert all(context.closed for context in tracked_sessions.contexts)


@pytest.mark.asyncio
async def test_generation_resolves_an_owned_material_from_its_authorized_storage_path(
    auth_api_client,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Generation consumes the owned material's stored file, never its UUID as a path."""
    from api import generate
    from config import get_settings

    user = await _register_user(auth_api_client, "material-owner@example.com")
    _use_tracking_stream_sessions(monkeypatch, auth_api_client.session_factory)
    settings = get_settings().model_copy(update={"upload_dir": tmp_path})
    captured: dict[str, object] = {}

    async def capture_stream(*_args, **kwargs):
        captured.update(kwargs)
        yield {"data": "complete"}

    monkeypatch.setattr(generate, "run_generation_stream", capture_stream)
    with patch("api.materials.get_settings", return_value=settings):
        upload = await auth_api_client.client.post(
            "/api/materials/upload",
            files={"file": ("notes.txt", b"owned sorting material", "text/plain")},
            headers=user["headers"],
        )
        assert upload.status_code == 201
        material_id = upload.json()["id"]
        project = await auth_api_client.client.post(
            "/api/projects",
            json={
                "title": "Material-backed project",
                "constraints": {"material_ids": [material_id]},
            },
            headers=user["headers"],
        )
        assert project.status_code == 201

        response = await auth_api_client.client.get(
            f"/api/projects/{project.json()['id']}/generate/stream",
            headers=user["headers"],
        )

    assert response.status_code == 200
    assert captured["materials"] == [
        {
            "material_id": material_id,
            "content_text": "owned sorting material",
            "topics": [],
        }
    ]


@pytest.mark.asyncio
async def test_generation_hides_foreign_missing_and_corrupt_material_paths(
    auth_api_client,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """All unusable material references fail privately before the stream service."""
    from api import generate
    from config import get_settings
    from db.models import Project, SourceMaterial

    user_a = await _register_user(auth_api_client, "material-owner-a@example.com")
    user_b = await _register_user(auth_api_client, "material-owner-b@example.com")
    _use_tracking_stream_sessions(monkeypatch, auth_api_client.session_factory)
    foreign_material_id = uuid4()
    corrupt_material_id = uuid4()
    missing_material_id = uuid4()
    foreign_project_id = uuid4()
    corrupt_project_id = uuid4()
    missing_project_id = uuid4()
    outside_path = tmp_path / "outside-upload-root.txt"
    outside_path.write_text("must not be read", encoding="utf-8")
    upload_root = tmp_path / "uploads"
    settings = get_settings().model_copy(update={"upload_dir": upload_root})
    service_calls: list[bool] = []

    async def unexpected_stream(*_args, **_kwargs):
        service_calls.append(True)
        if False:
            yield {"data": "unreachable"}

    monkeypatch.setattr(generate, "run_generation_stream", unexpected_stream)
    async with auth_api_client.session_factory() as session:
        session.add_all(
            [
                Project(
                    id=foreign_project_id,
                    owner_id=user_a["id"],
                    title="Foreign material reference",
                    audience="undergraduate_cs",
                    difficulty="intermediate",
                    status="draft",
                    dsl_snapshot={"constraints": {"material_ids": [str(foreign_material_id)]}},
                ),
                Project(
                    id=corrupt_project_id,
                    owner_id=user_a["id"],
                    title="Corrupt material reference",
                    audience="undergraduate_cs",
                    difficulty="intermediate",
                    status="draft",
                    dsl_snapshot={"constraints": {"material_ids": [str(corrupt_material_id)]}},
                ),
                Project(
                    id=missing_project_id,
                    owner_id=user_a["id"],
                    title="Missing material reference",
                    audience="undergraduate_cs",
                    difficulty="intermediate",
                    status="draft",
                    dsl_snapshot={"constraints": {"material_ids": [str(missing_material_id)]}},
                ),
                SourceMaterial(
                    id=foreign_material_id,
                    owner_id=user_b["id"],
                    project_id=foreign_project_id,
                    type="txt",
                    storage_path=str(outside_path),
                ),
                SourceMaterial(
                    id=corrupt_material_id,
                    owner_id=user_a["id"],
                    project_id=corrupt_project_id,
                    type="txt",
                    storage_path=str(outside_path),
                ),
            ]
        )
        await session.commit()

    with patch("api.materials.get_settings", return_value=settings):
        responses = [
            await auth_api_client.client.get(
                f"/api/projects/{project_id}/generate/stream",
                headers=user_a["headers"],
            )
            for project_id in (
                foreign_project_id,
                missing_project_id,
                corrupt_project_id,
            )
        ]

    assert [response.status_code for response in responses] == [404, 404, 404]
    assert responses[0].json() == responses[1].json() == responses[2].json()
    assert service_calls == []


def test_shared_redis_uses_a_noeviction_policy_for_authentication_state() -> None:
    compose = (
        Path(__file__).resolve().parents[2] / "docker-compose.yml"
    ).read_text(encoding="utf-8")

    assert "--maxmemory-policy noeviction" in compose
    assert "allkeys-lru" not in compose


def test_sqlalchemy_engine_hides_bound_parameters() -> None:
    from db.database import engine

    assert engine.sync_engine.hide_parameters is True


@pytest.mark.asyncio
async def test_request_logging_never_records_raw_exception_credentials(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from api.middleware import RequestLoggingMiddleware

    password = "learning2026"
    refresh_hash = "a" * 64
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "https",
            "path": "/api/auth/login",
            "raw_path": b"/api/auth/login",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 443),
        }
    )

    async def raise_sensitive_database_error(_request):
        raise RuntimeError(
            f"query parameters password={password} refresh_token_hash={refresh_hash}"
        )

    caplog.set_level(logging.ERROR, logger="api")
    with pytest.raises(RuntimeError):
        await RequestLoggingMiddleware(FastAPI()).dispatch(
            request, raise_sensitive_database_error
        )

    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert password not in messages
    assert refresh_hash not in messages
    assert "query parameters" not in messages
    assert "RuntimeError" in messages


@pytest.mark.asyncio
async def test_unhandled_http_errors_do_not_record_raw_exception_credentials(
    auth_api_client,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real exception-handler path must not render sensitive exception text."""
    password = "learning2026"
    refresh_hash = "b" * 64

    async def raise_sensitive_error(*_args, **_kwargs):
        raise RuntimeError(
            f"query parameters password={password} refresh_token_hash={refresh_hash}"
        )

    monkeypatch.setattr("api.auth.register_user", raise_sensitive_error)
    caplog.set_level(logging.ERROR)
    response = await auth_api_client.client.post(
        "/api/auth/register",
        json={
            "email": "logging@example.com",
            "nickname": "Logging",
            "password": password,
        },
    )

    assert response.status_code == 500
    assert password not in caplog.text
    assert refresh_hash not in caplog.text
    assert "query parameters" not in caplog.text


def test_alembic_excludes_reflected_baseline_only_tables_and_indexes() -> None:
    policy_path = Path(__file__).resolve().parents[1] / "db" / "alembic_policy.py"
    assert policy_path.is_file()
    if not policy_path.is_file():
        return

    from db.alembic_policy import BASELINE_MANAGED_TABLES, include_object

    assert BASELINE_MANAGED_TABLES == {
        "teaching_plans",
        "knowledge_base",
        "langgraph_checkpoints",
    }
    assert include_object(
        SimpleNamespace(name="knowledge_base"),
        "knowledge_base",
        "table",
        True,
        None,
    ) is False
    assert include_object(
        SimpleNamespace(table=SimpleNamespace(name="knowledge_base")),
        "idx_kb_embedding",
        "index",
        True,
        None,
    ) is False
    assert include_object(
        SimpleNamespace(table=SimpleNamespace(name="frames")),
        "idx_frames_project_order",
        "index",
        True,
        None,
    ) is True


def test_orm_metadata_tracks_baseline_indexes_for_orm_managed_tables() -> None:
    from db.alembic_policy import include_object
    from db.models import Base

    index_names = {
        index.name
        for table in Base.metadata.tables.values()
        for index in table.indexes
    }
    assert {
        "idx_frames_project_order",
        "idx_frames_frame_id",
        "idx_params_project",
        "idx_quality_project",
        "idx_export_status",
        "idx_feedback_project",
        "idx_feedback_frame",
        "idx_materials_project",
        "idx_versions_project",
        "idx_projects_status",
    } <= index_names
    assert include_object(
        SimpleNamespace(name="projects"), "projects", "table", True, None
    ) is True


def test_alembic_context_and_ci_check_protect_the_external_schema() -> None:
    agent_dir = Path(__file__).resolve().parents[1]
    env_source = (agent_dir / "alembic" / "env.py").read_text(encoding="utf-8")
    workflow = (
        agent_dir.parents[0] / ".github" / "workflows" / "backend-ci.yml"
    ).read_text(encoding="utf-8")

    assert env_source.count("include_object=include_object") == 2
    assert "python -m alembic check" in workflow
    assert workflow.index("Verify Alembic metadata has no drift") > workflow.index(
        "Upgrade database"
    )


def test_offline_upgrade_sql_keeps_external_baseline_objects() -> None:
    """Offline rendering must not introduce destructive external-table DDL."""
    agent_dir = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=agent_dir,
        check=True,
        capture_output=True,
        text=True,
    )

    for table_name in (
        "teaching_plans",
        "knowledge_base",
        "langgraph_checkpoints",
    ):
        assert f"DROP TABLE {table_name}" not in result.stdout
    assert "DROP INDEX idx_kb_embedding" not in result.stdout
