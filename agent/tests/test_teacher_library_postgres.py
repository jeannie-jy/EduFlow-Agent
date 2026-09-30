"""Opt-in real PostgreSQL tenant isolation and cascade regression test.

Run after Alembic migration with EDUFLOW_TEST_DATABASE_URL pointing to a
dedicated disposable database and EDUFLOW_TEST_DB_DISPOSABLE=1. This test never
calls an embedding provider.
"""

from __future__ import annotations

import os
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from services.knowledge_library import index_source, search_library
from services.teacher_library import (
    attach_material_to_project,
    detach_material_from_project,
    enable_library_material,
    list_project_materials,
    teacher_source_key,
)

TEST_URL = os.getenv("EDUFLOW_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_URL or os.getenv("EDUFLOW_TEST_DB_DISPOSABLE") != "1",
    reason="explicit disposable PostgreSQL test database not provided",
)


@pytest.mark.asyncio
async def test_two_teachers_multi_project_reuse_idempotency_and_delete_zero_recall():
    engine = create_async_engine(TEST_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    teacher_a, teacher_b = uuid.uuid4(), uuid.uuid4()
    project_a1, project_a2, project_b = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    material_a, material_b = uuid.uuid4(), uuid.uuid4()
    try:
        async with sessions() as session:
            for owner, name in ((teacher_a, "alpha"), (teacher_b, "beta")):
                await session.execute(text("""
                    INSERT INTO users (id, email, nickname, password_hash, role)
                    VALUES (:id, :email, :nickname, 'test-only', 'teacher')
                """), {"id": owner, "email": f"{name}-{owner}@isolated.example", "nickname": name})
            for project_id, owner in (
                (project_a1, teacher_a), (project_a2, teacher_a), (project_b, teacher_b)
            ):
                await session.execute(text("""
                    INSERT INTO projects (id, title, owner_id)
                    VALUES (:id, 'isolation test', :owner_id)
                """), {"id": project_id, "owner_id": str(owner)})
            for material_id, owner, title in (
                (material_a, teacher_a, "alpha-notes.pdf"),
                (material_b, teacher_b, "beta-notes.pdf"),
            ):
                await session.execute(text("""
                    INSERT INTO materials
                        (id, owner_id, original_filename, stored_filename,
                         media_type, size_bytes, status)
                    VALUES
                        (:id, :owner_id, :title, 'uploaded_test.pdf',
                         'application/pdf', 32, 'parsed')
                """), {"id": material_id, "owner_id": owner, "title": title})
            await session.commit()

        async with sessions() as session:
            await enable_library_material(session, material_id=material_a, owner_id=teacher_a)
            await enable_library_material(session, material_id=material_b, owner_id=teacher_b)
            await attach_material_to_project(
                session, project_id=project_a1, material_id=material_a, owner_id=teacher_a
            )
            await attach_material_to_project(
                session, project_id=project_a1, material_id=material_a, owner_id=teacher_a
            )
            await attach_material_to_project(
                session, project_id=project_b, material_id=material_b, owner_id=teacher_b
            )
            with pytest.raises(LookupError):
                await attach_material_to_project(
                    session, project_id=project_b, material_id=material_a, owner_id=teacher_a
                )
            with pytest.raises(LookupError):
                await attach_material_to_project(
                    session, project_id=project_b, material_id=material_a, owner_id=teacher_b
                )
            with pytest.raises(LookupError):
                await list_project_materials(session, project_id=project_b, owner_id=teacher_a)
            links = await list_project_materials(
                session, project_id=project_a1, owner_id=teacher_a
            )
            assert len(links) == 1
            assert links[0]["material_id"] == str(material_a)
            await session.commit()

        async with sessions() as session:
            chunks = [{
                "section": "第一章", "locator": "page:2;char:0-20",
                "content": "二分查找需要有序数组，逐次缩小搜索区间。",
            }]
            first = await index_source(
                session, source_key=teacher_source_key(material_a),
                scope="teacher", title="alpha-notes.pdf", version="v1",
                chunks=chunks, owner_id=teacher_a, material_id=material_a,
                allow_embedding=False, publish=True,
            )
            repeated = await index_source(
                session, source_key=teacher_source_key(material_a),
                scope="teacher", title="alpha-notes.pdf", version="v1",
                chunks=chunks, owner_id=teacher_a, material_id=material_a,
                allow_embedding=False, publish=True,
            )
            assert first["indexed"] is True and repeated["indexed"] is False
            await session.commit()

        async with sessions() as session:
            with patch("services.knowledge_library._canonical_credential_available", return_value=False):
                visible = await search_library(
                    session, "二分查找", owner_id=teacher_a, project_id=project_a1
                )
                wrong_project = await search_library(
                    session, "二分查找", owner_id=teacher_a, project_id=project_a2
                )
                wrong_teacher = await search_library(
                    session, "二分查找", owner_id=teacher_b, project_id=project_b
                )
            assert visible and visible[0]["locator"] == "page:2;char:0-20"
            assert visible[0]["title"] == "alpha-notes.pdf"
            assert wrong_project == [] and wrong_teacher == []
            await attach_material_to_project(
                session, project_id=project_a2, material_id=material_a, owner_id=teacher_a
            )
            await detach_material_from_project(
                session, project_id=project_a1, material_id=material_a, owner_id=teacher_a
            )
            await session.commit()

        async with sessions() as session:
            with patch("services.knowledge_library._canonical_credential_available", return_value=False):
                assert await search_library(
                    session, "二分查找", owner_id=teacher_a, project_id=project_a1
                ) == []
                assert await search_library(
                    session, "二分查找", owner_id=teacher_a, project_id=project_a2
                )
            await session.execute(
                text("DELETE FROM materials WHERE id = :id"), {"id": material_a}
            )
            await session.commit()

        async with sessions() as session:
            with patch("services.knowledge_library._canonical_credential_available", return_value=False):
                assert await search_library(
                    session, "二分查找", owner_id=teacher_a, project_id=project_a2
                ) == []
            count = (await session.execute(text("""
                SELECT count(*) FROM knowledge_sources WHERE material_id = :id
            """), {"id": material_a})).scalar_one()
            assert count == 0
    finally:
        await engine.dispose()
