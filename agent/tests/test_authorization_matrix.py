"""Cross-resource owner/admin policy matrix."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute

from api.auth import is_admin, require_project_owner
from api.jobs import _owned_job
from api.materials import _authorize_material


def _user(*, role: str = "teacher") -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), role=role)


def test_is_admin_uses_resolved_role() -> None:
    assert is_admin(_user(role="admin")) is True
    assert is_admin(_user(role="teacher")) is False
    assert is_admin(None) is False


def test_every_business_route_has_the_auth_boundary() -> None:
    from main import app

    public_prefixes = (
        "/api/auth/",
        "/api/health",
        "/api/ready",
        "/api/metrics",
        "/api/ping",
    )
    unprotected = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith("/api/"):
            continue
        if route.path.startswith(public_prefixes):
            continue
        dependency_calls = {dependency.call for dependency in route.dependant.dependencies}
        if require_project_owner not in dependency_calls:
            unprotected.append(route.path)
    assert unprotected == []


@pytest.mark.asyncio
async def test_project_boundary_hides_cross_owner_from_non_admin() -> None:
    user = _user()
    session = MagicMock()
    session.get = AsyncMock(return_value=SimpleNamespace(owner_id=str(uuid.uuid4())))
    request = MagicMock(path_params={"project_id": str(uuid.uuid4())})

    with pytest.raises(HTTPException) as caught:
        await require_project_owner(request, user, session)
    assert caught.value.status_code == 404


@pytest.mark.asyncio
async def test_admin_can_resolve_cross_owner_material() -> None:
    material = SimpleNamespace(owner_id=uuid.uuid4())
    session = MagicMock()
    session.get = AsyncMock(return_value=material)

    result = await _authorize_material(str(uuid.uuid4()), _user(role="admin"), session)

    assert result is material


@pytest.mark.asyncio
async def test_admin_background_job_lookup_bypasses_owner_filter() -> None:
    job_id = uuid.uuid4()
    job = SimpleNamespace(id=job_id)
    session = MagicMock()
    session.get = AsyncMock(return_value=job)
    session.scalar = AsyncMock()

    result = await _owned_job(session, job_id, _user(role="admin"))

    assert result is job
    session.get.assert_awaited_once()
    session.scalar.assert_not_awaited()


@pytest.mark.asyncio
async def test_non_admin_material_owner_mismatch_is_not_found() -> None:
    session = MagicMock()
    session.get = AsyncMock(return_value=SimpleNamespace(owner_id=uuid.uuid4()))

    with pytest.raises(HTTPException) as caught:
        await _authorize_material(str(uuid.uuid4()), _user(), session)
    assert caught.value.status_code == 404


@pytest.mark.asyncio
async def test_admin_export_status_reads_job_without_owner_join() -> None:
    from api.export import get_export_status

    job_id = uuid.uuid4()
    source_version_id = uuid.uuid4()
    job = SimpleNamespace(
        id=job_id,
        source_version_id=source_version_id,
        status="queued",
        progress_pct=0,
        artifacts=[],
        error_log=None,
        next_attempt_at=None,
    )
    session = MagicMock()
    session.get = AsyncMock(return_value=job)
    session.scalar = AsyncMock()
    with patch("api.export._get_redis", new=AsyncMock(return_value=None)):
        result = await get_export_status(
            str(job_id), session=session, current_user=_user(role="admin")
        )

    assert result["job_id"] == str(job_id)
    assert result["source_version_id"] == str(source_version_id)
    session.get.assert_awaited_once()
    session.scalar.assert_not_awaited()


@pytest.mark.asyncio
async def test_non_admin_export_lookup_uses_owner_join() -> None:
    from api.export import _owned_export_job

    session = MagicMock()
    session.get = AsyncMock()
    session.scalar = AsyncMock(return_value=None)
    result = await _owned_export_job(session, uuid.uuid4(), _user())

    assert result is None
    session.get.assert_not_awaited()
    session.scalar.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_download_of_missing_job_is_public_not_found() -> None:
    from api.export import download_artifact

    session = MagicMock()
    session.get = AsyncMock(return_value=None)
    with pytest.raises(HTTPException) as caught:
        await download_artifact(
            str(uuid.uuid4()),
            "output.mp4",
            session=session,
            current_user=_user(role="admin"),
        )
    assert caught.value.status_code == 404
