"""Disposable-DB end-to-end worker and tenant-scope acceptance test.

Run only with EDUFLOW_TEST_DATABASE_URL and EDUFLOW_TEST_DB_DISPOSABLE=1.
The test uses synthetic text and never calls a model or embedding provider.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from db.models import BackgroundJob, BackgroundJobAttempt
from services.knowledge_library import search_library
from services.task_worker import TASK_WORKER_ID, _execute_material_index
from services.teacher_library import attach_material_to_project, enable_library_material

TEST_URL = os.getenv("EDUFLOW_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_URL or os.getenv("EDUFLOW_TEST_DB_DISPOSABLE") != "1",
    reason="explicit disposable PostgreSQL test database not provided",
)


@pytest.mark.asyncio
async def test_long_markdown_worker_index_retry_is_idempotent_and_delete_is_zero_recall():
    engine = create_async_engine(TEST_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    owner, other = uuid.uuid4(), uuid.uuid4()
    project, other_project, material = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    content = (
        "# 第一章\n银杏检索锚点 是一条原创测试定义。\n"
        + "长文档内容。" * 28_000
        + "\n# 结尾\n尾页独特锚点 是原文最后一节。\n"
    )

    async def copy_fixture(_material, destination: Path) -> None:
        destination.write_text(content, encoding="utf-8")

    try:
        async with sessions() as session:
            for uid, label in ((owner, "owner"), (other, "other")):
                await session.execute(text("""
                    INSERT INTO users (id, email, nickname, password_hash, role)
                    VALUES (:id, :email, :nickname, 'test-only', 'teacher')
                """), {"id": uid, "email": f"{label}-{uid}@isolated.example", "nickname": label})
            for pid, uid in ((project, owner), (other_project, other)):
                await session.execute(text("""
                    INSERT INTO projects (id, title, owner_id)
                    VALUES (:id, 'index acceptance', :owner_id)
                """), {"id": pid, "owner_id": str(uid)})
            await session.execute(text("""
                INSERT INTO materials
                    (id, owner_id, original_filename, stored_filename,
                     media_type, size_bytes, status)
                VALUES
                    (:id, :owner_id, 'long-lecture.md', 'long-lecture.md',
                     'text/markdown', :size_bytes, 'uploaded')
            """), {
                "id": material, "owner_id": owner,
                "size_bytes": len(content.encode("utf-8")),
            })
            await session.commit()

        async with sessions() as session:
            await enable_library_material(session, material_id=material, owner_id=owner)
            await attach_material_to_project(
                session, project_id=project, material_id=material, owner_id=owner,
            )
            await session.commit()

        async def run_one(attempt: int) -> None:
            job_id = uuid.uuid4()
            async with sessions() as session:
                session.add(BackgroundJob(
                    id=job_id, owner_id=owner, kind="material_index",
                    idempotency_key=f"{material}:{attempt}",
                    payload={"material_id": str(material), "allow_embedding": False},
                    status="running", worker_id=TASK_WORKER_ID, attempt_count=1,
                ))
                session.add(BackgroundJobAttempt(
                    id=uuid.uuid4(), job_id=job_id, attempt_no=1,
                    worker_id=TASK_WORKER_ID, status="running",
                ))
                await session.commit()
            job = {
                "job_id": str(job_id), "owner_id": str(owner), "attempt_no": 1,
                "payload": {"material_id": str(material), "allow_embedding": False},
            }
            with (
                patch("db.database.async_session_factory", sessions),
                patch("api.materials._copy_material_to", side_effect=copy_fixture),
                patch("services.knowledge_library.generate_embedding") as embedding,
            ):
                await _execute_material_index(job)
            embedding.assert_not_called()
            async with sessions() as session:
                row = await session.get(BackgroundJob, job_id)
                assert row.status == "completed"

        await run_one(1)
        await run_one(2)

        async with sessions() as session:
            counts = (await session.execute(text("""
                SELECT count(DISTINCT v.id) AS versions, count(c.id) AS chunks
                FROM knowledge_sources s
                JOIN knowledge_versions v ON v.source_id = s.id
                JOIN knowledge_chunks c ON c.version_id = v.id
                WHERE s.material_id = :material
            """), {"material": material})).mappings().one()
            assert counts["versions"] == 1
            assert counts["chunks"] > 100
            with patch("services.knowledge_library._canonical_credential_available", return_value=False):
                tail = await search_library(
                    session, "尾页独特锚点", owner_id=owner, project_id=project,
                    scope_filter="teacher",
                )
                cross_project = await search_library(
                    session, "尾页独特锚点", owner_id=other, project_id=other_project,
                    scope_filter="teacher",
                )
            assert tail and tail[0]["title"] == "long-lecture.md"
            assert tail[0]["locator"].startswith("section:2")
            assert cross_project == []
            await session.execute(text("DELETE FROM materials WHERE id = :id"), {"id": material})
            await session.commit()

        async with sessions() as session:
            with patch("services.knowledge_library._canonical_credential_available", return_value=False):
                assert await search_library(
                    session, "尾页独特锚点", owner_id=owner, project_id=project,
                    scope_filter="teacher",
                ) == []
    finally:
        await engine.dispose()
