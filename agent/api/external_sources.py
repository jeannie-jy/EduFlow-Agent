"""Administrator-only external source allowlist and editorial release gate."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_session
from db.models import BackgroundJob, ExternalSourceAllowlist, ExternalSyncCandidate, User
from services.audit import record_audit
from services.external_sources import register_external_url
from services.knowledge_library import index_source, publish_version

from .auth import require_admin

router = APIRouter(prefix="/admin/external-sources", tags=["admin", "knowledge"])


class AllowlistInput(BaseModel):
    url: str = Field(min_length=15, max_length=2048)
    institution: str = Field(min_length=2, max_length=300)
    license_note: str = Field(min_length=5, max_length=2000)


class CandidateReview(BaseModel):
    title: str = Field(min_length=2, max_length=500)
    section: str = Field(min_length=1, max_length=500)
    document_version: str = Field(min_length=1, max_length=80)
    summary: str = Field(min_length=30, max_length=4000)
    author: str = Field(min_length=2, max_length=300)
    published_at: datetime | None = None
    license: str = Field(min_length=2, max_length=300)


class PublicationConfirmation(BaseModel):
    confirm_source_version: bool
    confirm_attribution: bool
    confirm_license: bool
    confirm_original_summary: bool


@router.post("/allowlist", status_code=201)
async def add_external_allowlist(
    body: AllowlistInput,
    session: AsyncSession = Depends(get_session),
    admin: Annotated[User, Depends(require_admin)] = None,
) -> dict:
    try:
        row = await register_external_url(
            session, url=body.url, institution=body.institution,
            license_note=body.license_note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    record_audit(
        session, action="external.allowlisted", resource_type="external_source",
        resource_id=str(row.id), actor_id=admin.id,
        details={"url": row.url},
    )
    return {"id": str(row.id), "url": row.url, "active": row.active}


@router.get("/allowlist")
async def list_external_allowlist(
    session: AsyncSession = Depends(get_session),
    _admin: Annotated[User, Depends(require_admin)] = None,
) -> dict:
    rows = (await session.scalars(select(ExternalSourceAllowlist).order_by(
        ExternalSourceAllowlist.created_at.desc()
    ))).all()
    return {"items": [{
        "id": str(row.id), "url": row.url, "institution": row.institution,
        "license_note": row.license_note, "active": row.active,
        "last_remote_checksum": row.last_remote_checksum,
        "last_checked_at": row.last_checked_at.isoformat() if row.last_checked_at else None,
        "last_error": row.last_error,
    } for row in rows]}


@router.post("/allowlist/{allowlist_id}/sync", status_code=202)
async def queue_external_sync(
    allowlist_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    admin: Annotated[User, Depends(require_admin)] = None,
) -> dict:
    row = await session.get(ExternalSourceAllowlist, allowlist_id)
    if row is None or not row.active:
        raise HTTPException(status_code=404, detail="Active external URL not found")
    job = BackgroundJob(
        id=uuid.uuid4(), kind="external_sync",
        idempotency_key=f"{allowlist_id}:{uuid.uuid4().hex}",
        owner_id=admin.id, project_id=None,
        payload={"allowlist_id": str(allowlist_id)}, status="queued",
    )
    session.add(job)
    record_audit(
        session, action="external.sync_queued", resource_type="external_source",
        resource_id=str(allowlist_id), actor_id=admin.id,
        details={"job_id": str(job.id)},
    )
    await session.flush()
    return {"job_id": str(job.id), "status": "queued"}


@router.get("/candidates")
async def list_external_candidates(
    session: AsyncSession = Depends(get_session),
    _admin: Annotated[User, Depends(require_admin)] = None,
) -> dict:
    rows = (await session.execute(text("""
        SELECT c.id, c.allowlist_id, c.status, c.remote_checksum, c.fetched_at,
               c.title, c.section, c.document_version, c.summary, c.author,
               c.published_at, c.license, a.url, a.institution, a.license_note
        FROM external_sync_candidates c
        JOIN external_source_allowlist a ON a.id = c.allowlist_id
        ORDER BY c.created_at DESC LIMIT 100
    """))).mappings().all()
    return {"items": [{key: value.isoformat() if isinstance(value, datetime) else str(value)
                       if isinstance(value, uuid.UUID) else value
                       for key, value in row.items()} for row in rows]}


@router.put("/candidates/{candidate_id}")
async def review_external_candidate(
    candidate_id: uuid.UUID, body: CandidateReview,
    session: AsyncSession = Depends(get_session),
    admin: Annotated[User, Depends(require_admin)] = None,
) -> dict:
    candidate = await session.get(ExternalSyncCandidate, candidate_id, with_for_update=True)
    if candidate is None:
        raise HTTPException(status_code=404, detail="External candidate not found")
    if candidate.status != "pending":
        raise HTTPException(status_code=409, detail="Reviewed candidates are immutable")
    for key, value in body.model_dump().items():
        setattr(candidate, key, value)
    record_audit(
        session, action="external.candidate_edited", resource_type="external_candidate",
        resource_id=str(candidate_id), actor_id=admin.id,
    )
    return {"id": str(candidate_id), "status": "pending"}


@router.post("/candidates/{candidate_id}/reject")
async def reject_external_candidate(
    candidate_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    admin: Annotated[User, Depends(require_admin)] = None,
) -> dict:
    candidate = await session.get(ExternalSyncCandidate, candidate_id, with_for_update=True)
    if candidate is None:
        raise HTTPException(status_code=404, detail="External candidate not found")
    if candidate.status != "pending":
        raise HTTPException(status_code=409, detail="Reviewed candidates are immutable")
    candidate.status = "rejected"
    candidate.reviewed_at = datetime.now(UTC)
    candidate.reviewed_by = admin.id
    record_audit(
        session, action="external.candidate_rejected", resource_type="external_candidate",
        resource_id=str(candidate_id), actor_id=admin.id,
    )
    return {"id": str(candidate_id), "status": "rejected"}


@router.post("/candidates/{candidate_id}/publish")
async def publish_external_candidate(
    candidate_id: uuid.UUID, body: PublicationConfirmation,
    session: AsyncSession = Depends(get_session),
    admin: Annotated[User, Depends(require_admin)] = None,
) -> dict:
    if not all(body.model_dump().values()):
        raise HTTPException(status_code=422, detail="All editorial and license confirmations are required")
    candidate = await session.get(ExternalSyncCandidate, candidate_id, with_for_update=True)
    if candidate is None:
        raise HTTPException(status_code=404, detail="External candidate not found")
    allowlist = await session.get(ExternalSourceAllowlist, candidate.allowlist_id, with_for_update=True)
    if (
        allowlist is None or not allowlist.active or candidate.status != "pending"
        or candidate.remote_checksum != allowlist.last_remote_checksum
        or candidate.fetched_at < datetime.now(UTC) - timedelta(days=7)
    ):
        raise HTTPException(status_code=409, detail="Candidate is not the current pending remote version")
    required = (candidate.title, candidate.section, candidate.document_version,
                candidate.summary, candidate.author, candidate.license)
    if not all(isinstance(value, str) and value.strip() for value in required):
        raise HTTPException(status_code=422, detail="Reviewed summary and provenance are incomplete")
    source_key = "external-" + hashlib.sha256(allowlist.url.encode("utf-8")).hexdigest()[:40]
    version = f"{candidate.document_version}:{candidate.remote_checksum[:12]}"
    metadata = {
        "institution": allowlist.institution,
        "remote_checksum": candidate.remote_checksum,
        "fetched_at": candidate.fetched_at.isoformat(),
        "published_at": candidate.published_at.isoformat() if candidate.published_at else None,
        "license_note": allowlist.license_note,
        "summary_origin": "administrator_authored",
    }
    result = await index_source(
        session, source_key=source_key, scope="external", title=candidate.title,
        version=version, chunks=[{
            "section": candidate.section, "locator": candidate.section,
            "content": candidate.summary.strip(),
        }], metadata=metadata, source_url=allowlist.url,
        source_type="official_document_summary", author=candidate.author,
        license_name=candidate.license, allow_embedding=False,
        publish=False, review_status="approved",
    )
    await publish_version(
        session, source_id=uuid.UUID(result["source_id"]),
        version_id=uuid.UUID(result["version_id"]),
    )
    await session.execute(text("""
        UPDATE knowledge_sources
        SET title = :title, author = :author, license = :license,
            metadata = CAST(:metadata AS jsonb), updated_at = :updated_at
        WHERE id = :source_id AND scope = 'external'
    """), {
        "title": candidate.title, "author": candidate.author,
        "license": candidate.license,
        "metadata": json.dumps(metadata, ensure_ascii=False),
        "updated_at": datetime.now(UTC),
        "source_id": uuid.UUID(result["source_id"]),
    })
    allowlist.source_id = uuid.UUID(result["source_id"])
    candidate.status = "approved"
    candidate.reviewed_at = datetime.now(UTC)
    candidate.reviewed_by = admin.id
    record_audit(
        session, action="external.candidate_published", resource_type="external_candidate",
        resource_id=str(candidate_id), actor_id=admin.id,
        details={"source_id": result["source_id"], "version_id": result["version_id"]},
    )
    return {"source_id": result["source_id"], "version_id": result["version_id"],
            "status": "published"}


@router.post("/allowlist/{allowlist_id}/retire")
async def retire_external_source(
    allowlist_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    admin: Annotated[User, Depends(require_admin)] = None,
) -> dict:
    row = await session.get(ExternalSourceAllowlist, allowlist_id, with_for_update=True)
    if row is None:
        raise HTTPException(status_code=404, detail="External URL not found")
    row.active = False
    if row.source_id:
        await session.execute(text("""
            UPDATE knowledge_sources SET status = 'retired' WHERE id = :source_id
        """), {"source_id": row.source_id})
    record_audit(
        session, action="external.retired", resource_type="external_source",
        resource_id=str(allowlist_id), actor_id=admin.id,
    )
    return {"id": str(allowlist_id), "status": "retired"}
