"""Ownership isolation tests for top-level project resources."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

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
