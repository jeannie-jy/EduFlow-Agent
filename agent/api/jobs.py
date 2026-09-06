"""Operational status and cancellation for durable background Agent jobs."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_session
from db.models import User
from services.audit import record_audit

from .auth import get_current_user, is_admin

router = APIRouter(prefix="/background-jobs", tags=["background-jobs"])


def _job_uuid(job_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(job_id)
    except (TypeError, ValueError, AttributeError) as exc:
        raise HTTPException(status_code=404, detail="Background job not found") from exc


async def _owned_job(session: AsyncSession, job_id: uuid.UUID, current_user):
    from db.models import BackgroundJob, Project

    if current_user is None or is_admin(current_user):
        return await session.get(BackgroundJob, job_id)
    return await session.scalar(
        select(BackgroundJob)
        .outerjoin(Project, Project.id == BackgroundJob.project_id)
        .where(
            BackgroundJob.id == job_id,
            or_(
                BackgroundJob.owner_id == current_user.id,
                Project.owner_id == str(current_user.id),
            ),
        )
    )


@router.get("/{job_id}")
async def get_background_job(
    job_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: Annotated[User | None, Depends(get_current_user)] = None,
) -> dict:
    job = await _owned_job(session, _job_uuid(job_id), current_user)
    if job is None:
        raise HTTPException(status_code=404, detail="Background job not found")
    return {
        "job_id": str(job.id),
        "kind": job.kind,
        "status": job.status,
        "attempt_count": job.attempt_count,
        "next_attempt_at": job.next_attempt_at.isoformat() if job.next_attempt_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "error_code": job.error_class if job.status == "failed" else None,
    }


@router.delete("/{job_id}", status_code=202)
async def cancel_background_job(
    job_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: Annotated[User | None, Depends(get_current_user)] = None,
) -> dict:
    from db.models import BackgroundJobAttempt

    job = await _owned_job(session, _job_uuid(job_id), current_user)
    if job is None:
        raise HTTPException(status_code=404, detail="Background job not found")
    if job.status == "cancelled":
        return {"job_id": str(job.id), "status": "cancelled"}
    if job.status in {"completed", "failed"}:
        raise HTTPException(status_code=409, detail="Background job is already terminal")
    now = datetime.now(timezone.utc)
    job.status = "cancelled"
    job.worker_id = None
    job.lease_expires_at = None
    job.next_attempt_at = None
    job.completed_at = now
    if job.kind == "material_parse":
        from db.models import Material

        try:
            material_id = uuid.UUID(str((job.payload or {}).get("material_id", "")))
        except (ValueError, TypeError, AttributeError):
            material_id = None
        if material_id is not None:
            material = await session.get(Material, material_id)
            if material is not None and material.status == "parse_queued":
                material.status = "uploaded"
    await session.execute(
        update(BackgroundJobAttempt)
        .where(
            BackgroundJobAttempt.job_id == job.id,
            BackgroundJobAttempt.status == "running",
        )
        .values(status="cancelled", finished_at=now)
    )
    record_audit(
        session,
        action="background_job.cancel",
        resource_type="background_job",
        resource_id=str(job.id),
        actor_id=current_user.id if current_user is not None else None,
        details={"kind": job.kind},
    )
    await session.commit()
    return {"job_id": str(job.id), "status": "cancelled"}
