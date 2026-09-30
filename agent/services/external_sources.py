"""Restricted external-document fingerprinting and editorial staging.

Remote pages are never copied into the index. A sync stores only a bounded
checksum/HTTP metadata and opens a candidate for an administrator-authored
summary; a separate review action is needed before it can be retrieved.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit, urlunsplit

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ExternalSourceAllowlist, ExternalSyncCandidate, KnowledgeSource

MAX_REMOTE_BYTES = 1_000_000
SYNC_INTERVAL = timedelta(days=1)
ALLOWED_PATHS = {
    "www.rfc-editor.org": ("/rfc/", "/info/"),
    "rfc-editor.org": ("/rfc/", "/info/"),
    "docs.python.org": ("/3/",),
    "www.postgresql.org": ("/docs/16/",),
    "xlinux.nist.gov": ("/dads/",),
    "developer.mozilla.org": ("/en-US/docs/",),
}


def validate_external_url(value: str) -> str:
    """Require an exact official host/path and reject URL parsing tricks."""
    if not isinstance(value, str) or len(value) > 2048 or value != value.strip():
        raise ValueError("invalid external source URL")
    try:
        parts = urlsplit(value)
        host = (parts.hostname or "").lower()
        port = parts.port
    except ValueError as exc:
        raise ValueError("invalid external source URL") from exc
    if (
        parts.scheme != "https" or host not in ALLOWED_PATHS
        or parts.username or parts.password or port is not None
        or parts.query or parts.fragment or "\\" in value
        or not any(parts.path.startswith(prefix) for prefix in ALLOWED_PATHS[host])
        or "%" in parts.path or "//" in parts.path
        or any(segment in {".", ".."} for segment in parts.path.split("/"))
    ):
        raise ValueError("external URL is outside the fixed official-source allowlist")
    return urlunsplit(("https", host, parts.path, "", ""))


@dataclass(frozen=True)
class ExternalFingerprint:
    checksum: str
    fetched_at: datetime
    etag: str | None
    last_modified: str | None


async def fetch_external_fingerprint(url: str, *, transport=None) -> ExternalFingerprint:
    """Fetch one exact URL, without redirects, cookies, proxy credentials or storage."""
    canonical = validate_external_url(url)
    async with httpx.AsyncClient(
        follow_redirects=False, trust_env=False, timeout=15.0,
        transport=transport,
        headers={"User-Agent": "EduFlow-RAG-source-check/1.0", "Accept": "text/html, text/plain"},
    ) as client, client.stream("GET", canonical) as response:
        if response.status_code != 200:
            raise ValueError(f"external source returned HTTP {response.status_code}")
        content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        if content_type not in {"text/html", "text/plain", "application/xhtml+xml"}:
            raise ValueError("external source is not a bounded text document")
        size = 0
        digest = hashlib.sha256()
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > MAX_REMOTE_BYTES:
                raise ValueError("external source exceeds the sync size limit")
            digest.update(chunk)
        if size == 0:
            raise ValueError("external source is empty")
        return ExternalFingerprint(
            checksum=digest.hexdigest(), fetched_at=datetime.now(UTC),
            etag=response.headers.get("etag", "")[:500] or None,
            last_modified=response.headers.get("last-modified", "")[:200] or None,
        )


async def register_external_url(
    session: AsyncSession, *, url: str, institution: str, license_note: str,
) -> ExternalSourceAllowlist:
    canonical = validate_external_url(url)
    if not institution.strip() or len(institution) > 300 or not license_note.strip():
        raise ValueError("institution and license review note are required")
    existing = await session.scalar(select(ExternalSourceAllowlist).where(
        ExternalSourceAllowlist.url == canonical
    ).with_for_update())
    if existing is not None:
        if not existing.active:
            raise ValueError("retired external URL cannot be reactivated without a new review workflow")
        existing.institution = institution.strip()
        existing.license_note = license_note.strip()
        return existing
    row = ExternalSourceAllowlist(
        id=uuid.uuid4(), url=canonical, institution=institution.strip(),
        license_note=license_note.strip(), active=True,
    )
    session.add(row)
    await session.flush()
    return row


async def record_external_fingerprint(
    session: AsyncSession, *, allowlist_id: uuid.UUID,
    fingerprint: ExternalFingerprint,
) -> ExternalSyncCandidate | None:
    """Create a non-retrievable candidate only when remote bytes have changed."""
    row = await session.get(ExternalSourceAllowlist, allowlist_id, with_for_update=True)
    if row is None or not row.active:
        raise LookupError("active external URL not found")
    now = datetime.now(UTC)
    row.last_checked_at = fingerprint.fetched_at
    row.next_sync_at = now + SYNC_INTERVAL
    row.last_error = None
    if row.last_remote_checksum == fingerprint.checksum:
        return None
    row.last_remote_checksum = fingerprint.checksum
    if row.source_id is not None:
        # Fail closed: do not keep serving a version whose remote bytes changed
        # while its replacement is still awaiting editorial review.
        await session.execute(update(KnowledgeSource).where(
            KnowledgeSource.id == row.source_id,
            KnowledgeSource.scope == "external",
        ).values(status="retired"))
    existing = await session.scalar(select(ExternalSyncCandidate).where(
        ExternalSyncCandidate.allowlist_id == allowlist_id,
        ExternalSyncCandidate.remote_checksum == fingerprint.checksum,
    ))
    if existing is not None:
        return existing
    candidate = ExternalSyncCandidate(
        id=uuid.uuid4(), allowlist_id=allowlist_id,
        remote_checksum=fingerprint.checksum, fetched_at=fingerprint.fetched_at,
        etag=fingerprint.etag, last_modified=fingerprint.last_modified,
        status="pending",
    )
    session.add(candidate)
    await session.flush()
    return candidate
