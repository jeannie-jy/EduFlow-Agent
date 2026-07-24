"""Ownership isolation tests for top-level project resources."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio


@dataclass(frozen=True)
class AuthenticatedClient:
    """Small request helper that consistently sends one user's bearer token."""

    client: object
    headers: dict[str, str]

    async def get(self, path: str):
        return await self.client.get(path, headers=self.headers)

    async def delete(self, path: str):
        return await self.client.delete(path, headers=self.headers)

    async def put(self, path: str, **kwargs):
        return await self.client.put(path, headers=self.headers, **kwargs)

    async def post(self, path: str, **kwargs):
        return await self.client.post(path, headers=self.headers, **kwargs)


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
    data = response.json()
    return {
        "id": UUID(data["user"]["id"]),
        "headers": {"Authorization": f"Bearer {data['access_token']}"},
    }


@pytest_asyncio.fixture
async def user_a(auth_api_client):
    return await _register_user(auth_api_client, "owner-a@example.com")


@pytest_asyncio.fixture
async def user_b(auth_api_client):
    return await _register_user(auth_api_client, "owner-b@example.com")


@pytest_asyncio.fixture
async def client_for_user_a(auth_api_client, user_a) -> AuthenticatedClient:
    return AuthenticatedClient(auth_api_client.client, user_a["headers"])


@pytest_asyncio.fixture
async def client_for_user_b(auth_api_client, user_b) -> AuthenticatedClient:
    return AuthenticatedClient(auth_api_client.client, user_b["headers"])


async def _create_project(auth_api_client, owner_id: UUID, title: str):
    from db.models import Project

    project = Project(
        id=uuid4(),
        owner_id=owner_id,
        title=title,
        audience="undergraduate_cs",
        difficulty="intermediate",
        status="draft",
        dsl_snapshot={},
    )
    async with auth_api_client.session_factory() as session:
        session.add(project)
        await session.commit()
    return project


@pytest_asyncio.fixture
async def project_owned_by_user_a(auth_api_client, user_a):
    return await _create_project(auth_api_client, user_a["id"], "User A project")


@pytest_asyncio.fixture
async def project_owned_by_user_b(auth_api_client, user_b):
    return await _create_project(auth_api_client, user_b["id"], "User B project")


@pytest.mark.asyncio
async def test_user_cannot_read_foreign_project(
    client_for_user_b,
    project_owned_by_user_a,
):
    response = await client_for_user_b.get(
        f"/api/projects/{project_owned_by_user_a.id}"
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_project_list_only_returns_current_user_projects(
    client_for_user_b,
    project_owned_by_user_a,
    project_owned_by_user_b,
):
    response = await client_for_user_b.get("/api/projects")

    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert ids == {str(project_owned_by_user_b.id)}
    assert response.json()["total"] == 1


@pytest.mark.asyncio
async def test_create_project_assigns_authenticated_user_as_owner(
    auth_api_client,
    client_for_user_a,
    user_a,
):
    from sqlalchemy import select

    response = await client_for_user_a.post(
        "/api/projects",
        json={"title": "Owned on creation"},
    )

    assert response.status_code == 201
    from db.models import Project

    async with auth_api_client.session_factory() as session:
        project = await session.scalar(
            select(Project).where(Project.id == UUID(response.json()["id"]))
        )
    assert project is not None
    assert project.owner_id == user_a["id"]


@pytest.mark.asyncio
async def test_foreign_project_delete_is_indistinguishable_from_missing_project(
    client_for_user_b,
    project_owned_by_user_a,
):
    foreign = await client_for_user_b.delete(
        f"/api/projects/{project_owned_by_user_a.id}"
    )
    missing = await client_for_user_b.delete(f"/api/projects/{uuid4()}")

    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json()


@pytest_asyncio.fixture
async def owned_business_resources(auth_api_client, user_a, tmp_path):
    """Create every nested resource needed to prove B cannot enumerate A's data."""
    from db.models import ExportJobModel, Feedback, Frame, ParameterModel, Project, ProjectVersion

    project_id = uuid4()
    frame_id = uuid4()
    version_id = uuid4()
    job_id = uuid4()
    artifact = tmp_path / "owner-a-private.py"
    artifact.write_text("private export", encoding="utf-8")
    project = Project(
        id=project_id,
        owner_id=user_a["id"],
        title="A's private project",
        audience="undergraduate_cs",
        difficulty="intermediate",
        status="draft",
        dsl_snapshot={
            "frames": [{"frame_id": "f_001"}],
            "parameters": [{"key": "speed", "label": "Speed"}],
        },
    )
    async with auth_api_client.session_factory() as session:
        session.add_all(
            [
                project,
                Frame(
                    id=frame_id,
                    project_id=project_id,
                    version=1,
                    frame_id="f_001",
                    order_index=1,
                    title="Private frame",
                    quality_status="pending",
                    is_locked=False,
                ),
                ParameterModel(
                    id=uuid4(),
                    project_id=project_id,
                    key="speed",
                    label="Speed",
                    param_type="number",
                    default_value={"value": 1},
                    current_value={"value": 1},
                ),
                Feedback(
                    id=uuid4(),
                    project_id=project_id,
                    type="suggestion",
                    content="Private feedback",
                ),
                ProjectVersion(
                    id=version_id,
                    project_id=project_id,
                    version=1,
                    dsl_snapshot={"frames": [{"frame_id": "f_001"}]},
                    change_summary="Private version",
                ),
                ExportJobModel(
                    id=job_id,
                    project_id=project_id,
                    target="manim_video",
                    status="completed",
                    config={},
                ),
            ]
        )
        await session.commit()
    return {
        "project_id": project_id,
        "frame_id": frame_id,
        "version_id": version_id,
        "job_id": job_id,
        "artifact": artifact,
    }


@pytest.mark.asyncio
async def test_user_cannot_access_any_foreign_business_project_route(
    client_for_user_b,
    owned_business_resources,
):
    """Every business API resolves a project through the authenticated owner."""
    project_id = owned_business_resources["project_id"]
    version_id = owned_business_resources["version_id"]
    requests = [
        ("get", f"/api/projects/{project_id}/frames", {}),
        ("put", f"/api/projects/{project_id}/frames/f_001", {"json": {"title": "stolen"}}),
        ("post", f"/api/projects/{project_id}/frames/f_001/lock", {"json": {"is_locked": True}}),
        ("get", f"/api/projects/{project_id}/parameters", {}),
        ("post", f"/api/projects/{project_id}/recompute", {"json": {"changed_params": {"speed": 2}}}),
        ("get", f"/api/projects/{project_id}/feedback", {}),
        ("post", f"/api/projects/{project_id}/feedback", {"json": {"type": "suggestion", "content": "stolen"}}),
        ("post", f"/api/projects/{project_id}/versions", {"json": {"change_summary": "stolen"}}),
        ("get", f"/api/projects/{project_id}/versions", {}),
        ("get", f"/api/projects/{project_id}/versions/{version_id}", {}),
        ("post", f"/api/projects/{project_id}/versions/{version_id}/restore", {}),
        ("post", f"/api/projects/{project_id}/generate", {"json": {"action": "full"}}),
        ("get", f"/api/projects/{project_id}/generate/stream", {}),
        ("get", f"/api/projects/{project_id}/generate/resume/stream", {}),
        ("post", f"/api/projects/{project_id}/generate/approve", {}),
        ("post", f"/api/projects/{project_id}/generate/reject", {"json": {"feedback": "stolen"}}),
        ("post", f"/api/projects/{project_id}/regenerate", {"json": {"scope": {"type": "from_frame"}}}),
        ("get", f"/api/projects/{project_id}/generate/regenerate/stream", {}),
        ("post", f"/api/projects/{project_id}/export/manim", {"json": {}}),
    ]

    for method, path, kwargs in requests:
        response = await getattr(client_for_user_b, method)(path, **kwargs)
        assert response.status_code == 404, f"{method.upper()} {path}: {response.text}"


@pytest.mark.asyncio
async def test_user_cannot_access_foreign_export_status_or_download(
    client_for_user_b,
    owned_business_resources,
    tmp_path,
):
    """Export-job lookup joins its project, before Redis or filesystem access."""
    from config import get_settings

    job_id = owned_business_resources["job_id"]
    artifact = owned_business_resources["artifact"]
    export_root = artifact.parent
    export_dir = export_root / str(job_id)
    export_dir.mkdir()
    moved_artifact = export_dir / artifact.name
    artifact.rename(moved_artifact)
    settings = get_settings().model_copy(update={"export_dir": export_root})

    with patch("api.export.get_settings", return_value=settings):
        status = await client_for_user_b.get(f"/api/export/{job_id}")
        download = await client_for_user_b.get(
            f"/api/export/{job_id}/download/{moved_artifact.name}"
        )

    assert status.status_code == 404
    assert download.status_code == 404


@pytest.mark.asyncio
async def test_knowledge_endpoints_require_authentication(auth_api_client):
    search = await auth_api_client.client.post(
        "/api/knowledge/search", json={"query": "bubble sort"}
    )
    templates = await auth_api_client.client.get("/api/knowledge/templates")

    assert search.status_code == 401
    assert templates.status_code == 401


@pytest.mark.asyncio
async def test_feedback_frame_must_belong_to_the_authorized_project(
    auth_api_client,
    client_for_user_a,
    project_owned_by_user_a,
    project_owned_by_user_b,
):
    """Foreign and missing frame IDs are indistinguishable and create nothing."""
    from sqlalchemy import select
    from db.models import Feedback, Frame

    foreign_frame_id = uuid4()
    async with auth_api_client.session_factory() as session:
        session.add(
            Frame(
                id=foreign_frame_id,
                project_id=project_owned_by_user_b.id,
                version=1,
                frame_id="foreign-frame",
                order_index=1,
                title="Other project frame",
                quality_status="pending",
                is_locked=False,
            )
        )
        await session.commit()

    request_body = {"type": "correction", "content": "wrong frame"}
    foreign = await client_for_user_a.post(
        f"/api/projects/{project_owned_by_user_a.id}/feedback",
        json={**request_body, "frame_id": str(foreign_frame_id)},
    )
    missing = await client_for_user_a.post(
        f"/api/projects/{project_owned_by_user_a.id}/feedback",
        json={**request_body, "frame_id": str(uuid4())},
    )

    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json()
    async with auth_api_client.session_factory() as session:
        feedback = list(
            await session.scalars(
                select(Feedback).where(
                    Feedback.project_id == project_owned_by_user_a.id
                )
            )
        )
    assert feedback == []


@pytest.mark.asyncio
async def test_changed_route_families_make_foreign_and_missing_projects_indistinguishable(
    client_for_user_b,
    owned_business_resources,
):
    """Representative business routes use the shared not-found contract."""
    foreign_project_id = owned_business_resources["project_id"]
    missing_project_id = uuid4()
    foreign_job_id = owned_business_resources["job_id"]

    foreign_frames = await client_for_user_b.get(
        f"/api/projects/{foreign_project_id}/frames"
    )
    missing_frames = await client_for_user_b.get(
        f"/api/projects/{missing_project_id}/frames"
    )
    foreign_generate = await client_for_user_b.post(
        f"/api/projects/{foreign_project_id}/generate", json={"action": "full"}
    )
    missing_generate = await client_for_user_b.post(
        f"/api/projects/{missing_project_id}/generate", json={"action": "full"}
    )
    foreign_export = await client_for_user_b.get(f"/api/export/{foreign_job_id}")
    missing_export = await client_for_user_b.get(f"/api/export/{uuid4()}")

    for foreign, missing in [
        (foreign_frames, missing_frames),
        (foreign_generate, missing_generate),
        (foreign_export, missing_export),
    ]:
        assert foreign.status_code == missing.status_code == 404
        assert foreign.json() == missing.json()


@pytest.mark.asyncio
async def test_foreign_requests_stop_before_generation_redis_filesystem_or_background_work(
    client_for_user_b,
    owned_business_resources,
):
    """Authorization precedes all external work for protected resources."""
    from pathlib import Path

    project_id = owned_business_resources["project_id"]
    job_id = owned_business_resources["job_id"]

    with (
        patch("api.generate.run_generation_stream") as generate_stream,
        patch("api.generate.resume_generation_stream") as resume_stream,
        patch("api.generate.run_regenerate_stream") as regenerate_stream,
        patch("api.export._get_redis", new_callable=AsyncMock) as get_redis,
        patch("api.export._schedule_export_fallback") as schedule_fallback,
        patch.object(Path, "exists", side_effect=AssertionError("filesystem accessed")) as exists,
    ):
        generation = await client_for_user_b.get(
            f"/api/projects/{project_id}/generate/stream"
        )
        resume = await client_for_user_b.get(
            f"/api/projects/{project_id}/generate/resume/stream"
        )
        regenerate = await client_for_user_b.get(
            f"/api/projects/{project_id}/generate/regenerate/stream"
        )
        create_export = await client_for_user_b.post(
            f"/api/projects/{project_id}/export/manim", json={}
        )
        export_status = await client_for_user_b.get(f"/api/export/{job_id}")
        download = await client_for_user_b.get(
            f"/api/export/{job_id}/download/owner-a-private.py"
        )

    for response in [generation, resume, regenerate, create_export, export_status, download]:
        assert response.status_code == 404
    generate_stream.assert_not_called()
    resume_stream.assert_not_called()
    regenerate_stream.assert_not_called()
    get_redis.assert_not_awaited()
    schedule_fallback.assert_not_called()
    exists.assert_not_called()


@pytest.mark.asyncio
async def test_owner_can_use_representative_changed_route_families(
    client_for_user_a,
    owned_business_resources,
):
    """Owner access stays functional against the real isolated database."""
    from config import get_settings

    project_id = owned_business_resources["project_id"]
    frame_id = owned_business_resources["frame_id"]
    version_id = owned_business_resources["version_id"]
    job_id = owned_business_resources["job_id"]
    artifact = owned_business_resources["artifact"]
    export_root = artifact.parent
    export_dir = export_root / str(job_id)
    export_dir.mkdir()
    stored_artifact = export_dir / artifact.name
    artifact.rename(stored_artifact)
    settings = get_settings().model_copy(update={"export_dir": export_root})

    assert (await client_for_user_a.get(f"/api/projects/{project_id}/frames")).status_code == 200
    assert (
        await client_for_user_a.put(
            f"/api/projects/{project_id}/frames/f_001", json={"title": "Owner edit"}
        )
    ).status_code == 200
    assert (
        await client_for_user_a.post(
            f"/api/projects/{project_id}/recompute", json={"changed_params": {"speed": 2}}
        )
    ).status_code == 202
    assert (
        await client_for_user_a.post(
            f"/api/projects/{project_id}/feedback",
            json={"type": "correction", "content": "Owner feedback", "frame_id": str(frame_id)},
        )
    ).status_code == 201
    assert (await client_for_user_a.get(f"/api/projects/{project_id}/versions")).status_code == 200
    assert (
        await client_for_user_a.get(f"/api/projects/{project_id}/versions/{version_id}")
    ).status_code == 200
    assert (
        await client_for_user_a.post(
            f"/api/projects/{project_id}/generate", json={"action": "full"}
        )
    ).status_code == 202

    with (
        patch("api.export._get_redis", new_callable=AsyncMock, return_value=None),
        patch("api.export._schedule_export_fallback") as schedule_fallback,
        patch("api.export.get_settings", return_value=settings),
    ):
        assert (
            await client_for_user_a.post(f"/api/projects/{project_id}/export/manim", json={})
        ).status_code == 201
        assert (await client_for_user_a.get(f"/api/export/{job_id}")).status_code == 200
        assert (
            await client_for_user_a.get(
                f"/api/export/{job_id}/download/{stored_artifact.name}"
            )
        ).status_code == 200
    schedule_fallback.assert_called_once()
    assert (await client_for_user_a.get("/api/knowledge/templates")).status_code == 200


@pytest.mark.asyncio
async def test_user_cannot_parse_or_preview_foreign_material(
    client_for_user_a,
    client_for_user_b,
    tmp_path,
):
    """Material parse and preview use an owner-filtered database lookup."""
    from config import get_settings

    settings = get_settings().model_copy(update={"upload_dir": tmp_path})
    with patch("api.materials.get_settings", return_value=settings):
        upload = await client_for_user_a.post(
            "/api/materials/upload",
            files={"file": ("owner-a.txt", b"private material", "text/plain")},
        )
        assert upload.status_code == 201
        material_id = upload.json()["id"]

        parse = await client_for_user_b.post(f"/api/materials/{material_id}/parse")
        preview = await client_for_user_b.get(f"/api/materials/{material_id}/preview")

    assert parse.status_code == 404
    assert preview.status_code == 404


@pytest.mark.asyncio
async def test_project_creation_binds_only_current_users_materials(
    auth_api_client,
    client_for_user_a,
    user_a,
    tmp_path,
):
    """Valid material IDs become bound to the newly created project."""
    from config import get_settings
    from db.models import SourceMaterial
    from sqlalchemy import select

    settings = get_settings().model_copy(update={"upload_dir": tmp_path})
    with patch("api.materials.get_settings", return_value=settings):
        upload = await client_for_user_a.post(
            "/api/materials/upload",
            files={"file": ("mine.txt", b"my material", "text/plain")},
        )
        assert upload.status_code == 201
        material_id = upload.json()["id"]
        response = await client_for_user_a.post(
            "/api/projects",
            json={
                "title": "Project with material",
                "constraints": {"material_ids": [material_id]},
            },
        )

    assert response.status_code == 201
    async with auth_api_client.session_factory() as session:
        material = await session.scalar(
            select(SourceMaterial).where(SourceMaterial.id == UUID(material_id))
        )
    assert material is not None
    assert material.owner_id == user_a["id"]
    assert material.project_id == UUID(response.json()["id"])


@pytest.mark.asyncio
async def test_project_creation_rejects_foreign_or_missing_materials(
    client_for_user_a,
    client_for_user_b,
    tmp_path,
):
    """A project cannot bind another user's or nonexistent material ID."""
    from config import get_settings

    settings = get_settings().model_copy(update={"upload_dir": tmp_path})
    with patch("api.materials.get_settings", return_value=settings):
        upload = await client_for_user_b.post(
            "/api/materials/upload",
            files={"file": ("not-mine.txt", b"private material", "text/plain")},
        )
        assert upload.status_code == 201
        foreign_material_id = upload.json()["id"]

        foreign = await client_for_user_a.post(
            "/api/projects",
            json={
                "title": "Foreign material",
                "constraints": {"material_ids": [foreign_material_id]},
            },
        )
        missing = await client_for_user_a.post(
            "/api/projects",
            json={
                "title": "Missing material",
                "constraints": {"material_ids": [str(uuid4())]},
            },
        )

    assert foreign.status_code == 400
    assert missing.status_code == 400


@pytest.mark.asyncio
async def test_project_creation_rejects_already_bound_material(
    auth_api_client,
    client_for_user_a,
    user_a,
    tmp_path,
):
    """An already-bound material cannot be silently rebound to another project."""
    from config import get_settings
    from db.models import Project, SourceMaterial
    from sqlalchemy import select

    settings = get_settings().model_copy(update={"upload_dir": tmp_path})
    with patch("api.materials.get_settings", return_value=settings):
        upload = await client_for_user_a.post(
            "/api/materials/upload",
            files={"file": ("once.txt", b"bind once", "text/plain")},
        )
        assert upload.status_code == 201
        material_id = upload.json()["id"]
        first = await client_for_user_a.post(
            "/api/projects",
            json={
                "title": "Initially bound",
                "constraints": {"material_ids": [material_id]},
            },
        )
        second = await client_for_user_a.post(
            "/api/projects",
            json={
                "title": "Must not claim the material",
                "constraints": {"material_ids": [material_id]},
            },
        )

    assert first.status_code == 201
    assert second.status_code == 400
    async with auth_api_client.session_factory() as session:
        material = await session.scalar(
            select(SourceMaterial).where(SourceMaterial.id == UUID(material_id))
        )
        projects = list(
            (await session.scalars(select(Project).where(Project.owner_id == user_a["id"])))
        )
    assert material is not None
    assert material.project_id == UUID(first.json()["id"])
    assert [project.title for project in projects] == ["Initially bound"]


@pytest.mark.asyncio
async def test_project_material_lookup_locks_only_unbound_owned_rows():
    """The binding query protects unbound rows against concurrent rebinding."""
    from sqlalchemy.dialects import postgresql
    from api.projects import create_project
    from db.models import SourceMaterial
    from schema.project import ProjectCreateRequest

    user_id = uuid4()
    material_id = uuid4()
    material = SourceMaterial(id=material_id, owner_id=user_id, type="txt")
    result = MagicMock()
    result.scalars.return_value = [material]
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session.flush = AsyncMock()

    await create_project(
        ProjectCreateRequest(
            title="Lock material",
            constraints={"material_ids": [str(material_id)]},
        ),
        SimpleNamespace(id=user_id),
        session,
    )

    statement = session.execute.await_args.args[0]
    compiled = str(statement.compile(dialect=postgresql.dialect()))
    assert "source_materials.project_id IS NULL" in compiled
    assert "FOR UPDATE" in compiled


@pytest.mark.asyncio
async def test_corrupted_material_path_outside_upload_root_is_not_accessible(
    auth_api_client,
    client_for_user_a,
    tmp_path,
):
    """Parse and preview reject a database path that escapes the upload root."""
    from config import get_settings
    from db.models import SourceMaterial
    from sqlalchemy import select

    outside_path = tmp_path.parent / "outside.txt"
    outside_path.write_text("must not be read", encoding="utf-8")
    settings = get_settings().model_copy(update={"upload_dir": tmp_path})
    with patch("api.materials.get_settings", return_value=settings):
        upload = await client_for_user_a.post(
            "/api/materials/upload",
            files={"file": ("inside.txt", b"inside", "text/plain")},
        )
        assert upload.status_code == 201
        material_id = upload.json()["id"]
        async with auth_api_client.session_factory() as session:
            material = await session.scalar(
                select(SourceMaterial).where(SourceMaterial.id == UUID(material_id))
            )
            assert material is not None
            material.storage_path = str(outside_path)
            await session.commit()

        parse = await client_for_user_a.post(f"/api/materials/{material_id}/parse")
        preview = await client_for_user_a.get(f"/api/materials/{material_id}/preview")

    assert parse.status_code == preview.status_code == 404
    assert parse.json() == preview.json()
