"""HMAC-signed, hash-chained audit archives with verify-before-purge semantics."""

from __future__ import annotations

import hashlib
import hmac
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AuditEvent
from services.artifact_store import ArtifactStore
from services.audit import record_audit

_ZERO_HASH = "0" * 64


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _event_record(event: AuditEvent) -> dict[str, Any]:
    created_at = event.created_at
    if created_at is not None and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return {
        "id": event.id,
        "actor_id": str(event.actor_id) if event.actor_id else None,
        "action": event.action,
        "resource_type": event.resource_type,
        "resource_id": event.resource_id,
        "request_id": event.request_id,
        "details": event.details,
        "created_at": created_at.isoformat() if created_at else None,
    }


def build_archive(events: list[AuditEvent], signing_key: bytes) -> tuple[bytes, dict[str, Any]]:
    if len(signing_key) < 32:
        raise ValueError("Audit archive HMAC key must contain at least 32 bytes")
    previous_hash = _ZERO_HASH
    lines: list[bytes] = []
    for event in events:
        record = _event_record(event)
        event_hash = hashlib.sha256(
            bytes.fromhex(previous_hash) + _canonical(record)
        ).hexdigest()
        envelope = {
            "previous_hash": previous_hash,
            "event_hash": event_hash,
            "record": record,
        }
        lines.append(_canonical(envelope))
        previous_hash = event_hash
    archive_bytes = b"\n".join(lines) + (b"\n" if lines else b"")
    unsigned_manifest = {
        "schema_version": 1,
        "algorithm": "sha256-chain+hmac-sha256",
        "event_count": len(events),
        "first_event_id": events[0].id if events else None,
        "last_event_id": events[-1].id if events else None,
        "root_hash": previous_hash,
        "archive_sha256": hashlib.sha256(archive_bytes).hexdigest(),
    }
    signature = hmac.new(signing_key, _canonical(unsigned_manifest), hashlib.sha256).hexdigest()
    return archive_bytes, {**unsigned_manifest, "hmac_sha256": signature}


def verify_archive(archive_bytes: bytes, manifest: dict[str, Any], signing_key: bytes) -> None:
    supplied_signature = str(manifest.get("hmac_sha256", ""))
    unsigned = {key: value for key, value in manifest.items() if key != "hmac_sha256"}
    expected_signature = hmac.new(signing_key, _canonical(unsigned), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(supplied_signature, expected_signature):
        raise ValueError("Audit archive manifest signature mismatch")
    if hashlib.sha256(archive_bytes).hexdigest() != manifest.get("archive_sha256"):
        raise ValueError("Audit archive content digest mismatch")

    previous_hash = _ZERO_HASH
    count = 0
    first_id = None
    last_id = None
    for raw_line in archive_bytes.splitlines():
        envelope = json.loads(raw_line)
        if envelope.get("previous_hash") != previous_hash:
            raise ValueError("Audit archive chain link mismatch")
        expected_hash = hashlib.sha256(
            bytes.fromhex(previous_hash) + _canonical(envelope.get("record"))
        ).hexdigest()
        if not hmac.compare_digest(str(envelope.get("event_hash", "")), expected_hash):
            raise ValueError("Audit archive event hash mismatch")
        previous_hash = expected_hash
        event_id = envelope["record"]["id"]
        first_id = event_id if first_id is None else first_id
        last_id = event_id
        count += 1
    if (
        count != manifest.get("event_count")
        or first_id != manifest.get("first_event_id")
        or last_id != manifest.get("last_event_id")
        or previous_hash != manifest.get("root_hash")
    ):
        raise ValueError("Audit archive manifest metadata mismatch")


async def archive_audit_events(
    session: AsyncSession,
    store: ArtifactStore,
    *,
    before: datetime,
    signing_key: bytes,
    max_events: int,
    purge_after_verify: bool,
) -> dict[str, Any]:
    events = list((await session.execute(
        select(AuditEvent)
        .where(AuditEvent.created_at < before)
        .order_by(AuditEvent.id.asc())
        .limit(max_events)
        .with_for_update()
    )).scalars().all())
    if not events:
        return {"event_count": 0, "purged": 0, "archive_key": None, "manifest_key": None}

    archive_bytes, manifest = build_archive(events, signing_key)
    prefix = (
        f"audit-archives/{before.astimezone(timezone.utc).date().isoformat()}/"
        f"{events[0].id}-{events[-1].id}-{manifest['root_hash'][:16]}"
    )
    archive_key = f"{prefix}.jsonl"
    manifest_key = f"{prefix}.manifest.json"
    with tempfile.TemporaryDirectory(prefix="eduflow-audit-") as temp_dir:
        archive_path = Path(temp_dir) / "events.jsonl"
        manifest_path = Path(temp_dir) / "manifest.json"
        archive_path.write_bytes(archive_bytes)
        manifest_path.write_bytes(_canonical(manifest))
        await store.put_file(archive_key, archive_path, "application/x-ndjson")
        await store.put_file(manifest_key, manifest_path, "application/json")

        downloaded_archive = Path(temp_dir) / "verify-events.jsonl"
        downloaded_manifest = Path(temp_dir) / "verify-manifest.json"
        await store.get_file(archive_key, downloaded_archive)
        await store.get_file(manifest_key, downloaded_manifest)
        verified_manifest = json.loads(downloaded_manifest.read_bytes())
        verify_archive(downloaded_archive.read_bytes(), verified_manifest, signing_key)

    purged = 0
    if purge_after_verify:
        result = await session.execute(
            delete(AuditEvent).where(AuditEvent.id.in_([event.id for event in events]))
        )
        purged = int(result.rowcount or 0)
    record_audit(
        session,
        action="audit.archive.create",
        resource_type="audit_archive",
        resource_id=manifest["root_hash"],
        details={
            "archive_key": archive_key,
            "manifest_key": manifest_key,
            "event_count": len(events),
            "first_event_id": events[0].id,
            "last_event_id": events[-1].id,
            "purged": purged,
        },
    )
    await session.flush()
    return {
        "event_count": len(events),
        "purged": purged,
        "archive_key": archive_key,
        "manifest_key": manifest_key,
        "root_hash": manifest["root_hash"],
    }
