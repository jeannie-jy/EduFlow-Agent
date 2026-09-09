"""Cryptographic archive and verify-before-purge tests."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from db.models import AuditEvent, User
from services.artifact_store import LocalArtifactStore
from services.audit_archive import archive_audit_events, build_archive, verify_archive

KEY = b"test-audit-signing-key-at-least-32-bytes"


def _event(event_id: int, details=None):
    return SimpleNamespace(
        id=event_id,
        actor_id=None,
        action="project.update",
        resource_type="project",
        resource_id="project-1",
        request_id="request-1",
        details=details or {"field": "title"},
        created_at=datetime(2026, 1, event_id, tzinfo=timezone.utc),
    )


def test_hash_chain_and_hmac_detect_archive_tampering():
    archive, manifest = build_archive([_event(1), _event(2)], KEY)
    verify_archive(archive, manifest, KEY)

    parsed = json.loads(archive.splitlines()[0])
    parsed["record"]["action"] = "tampered"
    tampered = json.dumps(parsed, sort_keys=True).encode() + b"\n" + archive.split(b"\n", 1)[1]
    with pytest.raises(ValueError, match="digest mismatch"):
        verify_archive(tampered, manifest, KEY)


def test_archive_rejects_weak_signing_key():
    with pytest.raises(ValueError, match="at least 32 bytes"):
        build_archive([_event(1)], b"short")


@pytest_asyncio.fixture
async def audit_db():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(User.__table__.create)
        await connection.run_sync(AuditEvent.__table__.create)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_archive_is_download_verified_before_exact_rows_are_purged(audit_db, tmp_path):
    old = datetime.now(timezone.utc) - timedelta(days=100)
    audit_db.add_all([
        AuditEvent(
            actor_id=None,
            action="project.create",
            resource_type="project",
            resource_id="one",
            request_id="request-1",
            details={"safe": True},
            created_at=old,
        ),
        AuditEvent(
            actor_id=None,
            action="project.update",
            resource_type="project",
            resource_id="two",
            request_id="request-2",
            details={"safe": True},
            created_at=old,
        ),
    ])
    await audit_db.flush()
    store = LocalArtifactStore(tmp_path / "objects")

    result = await archive_audit_events(
        audit_db,
        store,
        before=datetime.now(timezone.utc) - timedelta(days=90),
        signing_key=KEY,
        max_events=100,
        purge_after_verify=True,
    )

    assert result["event_count"] == 2
    assert result["purged"] == 2
    remaining = list((await audit_db.execute(select(AuditEvent))).scalars().all())
    assert len(remaining) == 1
    assert remaining[0].action == "audit.archive.create"
    archive = (tmp_path / "objects" / result["archive_key"]).read_bytes()
    manifest = json.loads((tmp_path / "objects" / result["manifest_key"]).read_bytes())
    verify_archive(archive, manifest, KEY)
