"""Ownership isolation tests for top-level project resources."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4
from unittest.mock import patch

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
