"""Disposable PostgreSQL acceptance for private sync, review and withdrawal."""

from __future__ import annotations

import hashlib
import os
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.external_sources import (
    AllowlistInput,
    CandidateReview,
    PublicationConfirmation,
    add_external_allowlist,
    publish_external_candidate,
    queue_external_sync,
    retire_external_source,
    review_external_candidate,
)
from db.models import BackgroundJob, BackgroundJobAttempt, ExternalSyncCandidate
from services.external_sources import ExternalFingerprint, record_external_fingerprint
from services.knowledge_library import search_library
from services.task_worker import TASK_WORKER_ID, _execute_external_sync, queue_due_external_syncs

TEST_URL = os.getenv("EDUFLOW_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_URL or os.getenv("EDUFLOW_TEST_DB_DISPOSABLE") != "1",
    reason="explicit disposable PostgreSQL test database not provided",
)


@pytest.mark.asyncio
async def test_external_change_is_private_until_review_and_retirement_removes_recall():
    engine = create_async_engine(TEST_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    admin = SimpleNamespace(id=uuid.uuid4())
    url = f"https://www.postgresql.org/docs/16/synthetic-{uuid.uuid4().hex}.html"
    fp = ExternalFingerprint(
        checksum=hashlib.sha256(b"synthetic-official-fixture-v1").hexdigest(),
        fetched_at=datetime.now(UTC), etag='"v1"', last_modified=None,
    )
    try:
        async with sessions() as session:
            await session.execute(text("""
                INSERT INTO users (id, email, nickname, password_hash, role)
                VALUES (:id, :email, 'editor', 'test-only', 'admin')
            """), {"id": admin.id, "email": f"editor-{admin.id}@isolated.example"})
            await session.commit()
        async with sessions() as session:
            allowlisted = await add_external_allowlist(
                AllowlistInput(
                    url=url, institution="PostgreSQL Global Development Group",
                    license_note="PostgreSQL License checked; only an original summary is indexed",
                ), session, admin,
            )
            allowlist_id = uuid.UUID(allowlisted["id"])
            queued = await queue_external_sync(allowlist_id, session, admin)
            await session.commit()

        with patch("db.database.async_session_factory", sessions):
            assert await queue_due_external_syncs() == 1
            assert await queue_due_external_syncs() == 0

        job_id = uuid.UUID(queued["job_id"])
        async with sessions() as session:
            job = await session.get(BackgroundJob, job_id)
            job.status = "running"
            job.worker_id = TASK_WORKER_ID
            job.attempt_count = 1
            session.add(BackgroundJobAttempt(
                id=uuid.uuid4(), job_id=job_id, attempt_no=1,
                worker_id=TASK_WORKER_ID, status="running",
            ))
            await session.commit()
        with (
            patch("db.database.async_session_factory", sessions),
            patch("services.external_sources.fetch_external_fingerprint", new=AsyncMock(return_value=fp)) as fetch,
        ):
            await _execute_external_sync({
                "job_id": str(job_id), "attempt_no": 1,
                "payload": {"allowlist_id": str(allowlist_id)},
            })
        fetch.assert_awaited_once_with(url)

        async with sessions() as session:
            candidate = await session.scalar(select(ExternalSyncCandidate).where(
                ExternalSyncCandidate.allowlist_id == allowlist_id,
            ))
            assert candidate is not None and candidate.status == "pending"
            with patch("services.knowledge_library._canonical_credential_available", return_value=False):
                assert await search_library(session, "合成B树索引锚点") == []
            await review_external_candidate(
                candidate.id,
                CandidateReview(
                    title="PostgreSQL 16 索引类型", section="11.2 索引类型",
                    document_version="16", author="PostgreSQL Global Development Group",
                    license="PostgreSQL License", published_at=None,
                    summary="合成B树索引锚点：这是测试人员原创的索引类型摘要，不包含网页原文，"
                            "仅用于验证外部来源的待审、发布和撤回流程。",
                ), session, admin,
            )
            await session.commit()
            with patch("services.knowledge_library._canonical_credential_available", return_value=False):
                assert await search_library(session, "合成B树索引锚点") == []
            candidate_id = candidate.id

        async with sessions() as session:
            with pytest.raises(HTTPException) as missing:
                await publish_external_candidate(
                    candidate_id,
                    PublicationConfirmation(
                        confirm_source_version=True, confirm_attribution=True,
                        confirm_license=False, confirm_original_summary=True,
                    ), session, admin,
                )
            assert missing.value.status_code == 422
            with patch("services.knowledge_library.generate_embedding") as embedding:
                result = await publish_external_candidate(
                    candidate_id,
                    PublicationConfirmation(
                        confirm_source_version=True, confirm_attribution=True,
                        confirm_license=True, confirm_original_summary=True,
                    ), session, admin,
                )
            embedding.assert_not_called()
            assert result["status"] == "published"
            await session.commit()

        async with sessions() as session:
            with patch("services.knowledge_library._canonical_credential_available", return_value=False):
                visible = await search_library(session, "合成B树索引锚点")
            assert visible and visible[0]["source_url"] == url
            assert visible[0]["version"].startswith("16:")
            assert visible[0]["section"] == "11.2 索引类型"
            assert visible[0]["author"] == "PostgreSQL Global Development Group"
            assert visible[0]["license"] == "PostgreSQL License"
            assert await record_external_fingerprint(
                session, allowlist_id=allowlist_id, fingerprint=fp,
            ) is None
            await session.commit()
            count = (await session.execute(text("""
                SELECT count(*) FROM external_sync_candidates WHERE allowlist_id = :id
            """), {"id": allowlist_id})).scalar_one()
            assert count == 1

            changed = ExternalFingerprint(
                checksum=hashlib.sha256(b"synthetic-official-fixture-v2").hexdigest(),
                fetched_at=datetime.now(UTC), etag='"v2"', last_modified=None,
            )
            replacement = await record_external_fingerprint(
                session, allowlist_id=allowlist_id, fingerprint=changed,
            )
            assert replacement is not None and replacement.status == "pending"
            await session.commit()
            with patch("services.knowledge_library._canonical_credential_available", return_value=False):
                assert await search_library(session, "合成B树索引锚点") == []
            replacement_id = replacement.id

        async with sessions() as session:
            await review_external_candidate(
                replacement_id,
                CandidateReview(
                    title="PostgreSQL 16 索引类型", section="11.2 索引类型",
                    document_version="16.15", author="PostgreSQL Global Development Group",
                    license="PostgreSQL License", published_at=None,
                    summary="合成B树索引锚点：远端页面变化后，管理员重新撰写并复核的第二版摘要。"
                            "本句是测试原创内容，而非自动复制网页正文。",
                ), session, admin,
            )
            published_replacement = await publish_external_candidate(
                replacement_id,
                PublicationConfirmation(
                    confirm_source_version=True, confirm_attribution=True,
                    confirm_license=True, confirm_original_summary=True,
                ), session, admin,
            )
            assert published_replacement["status"] == "published"
            await session.commit()
            with patch("services.knowledge_library._canonical_credential_available", return_value=False):
                updated = await search_library(session, "合成B树索引锚点")
            assert updated and updated[0]["version"].startswith("16.15:")

        async with sessions() as session:
            await retire_external_source(allowlist_id, session, admin)
            await session.commit()
        async with sessions() as session:
            with patch("services.knowledge_library._canonical_credential_available", return_value=False):
                assert await search_library(session, "合成B树索引锚点") == []
    finally:
        await engine.dispose()
