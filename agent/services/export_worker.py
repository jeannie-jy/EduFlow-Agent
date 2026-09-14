"""Durable database-backed export worker.

Run as ``python -m services.export_worker`` in a separately constrained
container. API processes only enqueue jobs and never execute generated Python.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import signal
import socket
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, or_, select, update

from config import get_settings

logger = logging.getLogger(__name__)
WORKER_ID = os.getenv("EDUFLOW_WORKER_ID") or f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"


async def claim_export_job() -> dict[str, Any] | None:
    from db.database import async_session_factory
    from db.models import ExportJobAttempt, ExportJobModel, Project, ProjectVersion
    from services.project_persistence import load_canonical_project_dsl

    settings = get_settings()
    now = datetime.now(timezone.utc)
    async with async_session_factory() as session:
        # A worker that repeatedly dies eventually leaves a terminal, inspectable
        # record instead of an immortal ``rendering`` row.
        # Do this row-by-row instead of a bulk update so the quota reservation
        # reaches a terminal state even when the worker disappeared after its
        # last heartbeat.  Otherwise a permanently failed render would keep
        # consuming the user's daily/monthly video allowance forever.
        expired_result = await session.execute(
            select(ExportJobModel)
            .where(
                ExportJobModel.status == "rendering",
                ExportJobModel.lease_expires_at < now,
                ExportJobModel.attempt_count >= settings.export_worker_max_attempts,
            )
            .with_for_update(skip_locked=True)
        )
        expired_jobs = list(expired_result.scalars().all())
        if expired_jobs:
            from services.quota import settle_quota

            for expired in expired_jobs:
                await session.execute(
                    update(ExportJobAttempt)
                    .where(
                        ExportJobAttempt.job_id == expired.id,
                        ExportJobAttempt.status == "rendering",
                    )
                    .values(
                        status="failed",
                        finished_at=now,
                        error_class="lease_expired",
                    )
                )
                expired.status = "failed"
                expired.error_log = "Export worker lease expired after maximum attempts"
                expired.worker_id = None
                expired.lease_expires_at = None
                expired.next_attempt_at = None
                expired.completed_at = now
                expired.failure_retryable = False
                quota_ref = (expired.config or {}).get("quota_ref") if isinstance(expired.config, dict) else None
                quota_key = quota_ref.get("idempotency_key") if isinstance(quota_ref, dict) else None
                if isinstance(quota_key, str) and quota_key:
                    project = await session.get(Project, expired.project_id)
                    if project is not None and project.owner_id:
                        quota_user_id = quota_ref.get("user_id") if isinstance(quota_ref, dict) else None
                        try:
                            admitted_user_id = uuid.UUID(str(quota_user_id or project.owner_id))
                        except (TypeError, ValueError):
                            admitted_user_id = uuid.UUID(str(project.owner_id))
                        await settle_quota(
                            session,
                            user_id=admitted_user_id,
                            resource="video",
                            idempotency_key=quota_key,
                        )
        result = await session.execute(
            select(ExportJobModel)
            .where(
                ExportJobModel.attempt_count < settings.export_worker_max_attempts,
                or_(
                    and_(
                        ExportJobModel.status == "queued",
                        or_(
                            ExportJobModel.next_attempt_at.is_(None),
                            ExportJobModel.next_attempt_at <= now,
                        ),
                    ),
                    and_(
                        ExportJobModel.status == "rendering",
                        ExportJobModel.lease_expires_at < now,
                    ),
                ),
            )
            .order_by(ExportJobModel.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        job = result.scalar_one_or_none()
        if job is None:
            await session.commit()
            return None
        source_version_id = getattr(job, "source_version_id", None)
        project = await session.get(Project, job.project_id)
        owner_id = str(project.owner_id) if project is not None and project.owner_id else None
        if isinstance(source_version_id, uuid.UUID):
            source_version = await session.get(ProjectVersion, source_version_id)
            dsl = (
                dict(source_version.dsl_snapshot)
                if source_version is not None
                and source_version.project_id == job.project_id
                else None
            )
        else:
            # Compatibility path for jobs created before migration 0017.
            dsl = await load_canonical_project_dsl(project, session) if project else None
        if dsl is None:
            # The job can become unrenderable after enqueue (for example when
            # its project is removed during the deletion cooling-off period).
            # Release an unstarted reservation; a job that had already been
            # rendering is charged as an attempted/settled task.
            quota_ref = (job.config or {}).get("quota_ref") if isinstance(job.config, dict) else None
            quota_key = quota_ref.get("idempotency_key") if isinstance(quota_ref, dict) else None
            if isinstance(quota_key, str) and quota_key and owner_id:
                from services.quota import release_quota, settle_quota
                quota_user_id = quota_ref.get("user_id") if isinstance(quota_ref, dict) else None
                try:
                    admitted_user_id = uuid.UUID(str(quota_user_id or owner_id))
                except (TypeError, ValueError):
                    admitted_user_id = uuid.UUID(owner_id)

                if job.status in {"queued", "preparing"}:
                    await release_quota(
                        session,
                        user_id=admitted_user_id,
                        resource="video",
                        idempotency_key=quota_key,
                    )
                else:
                    await settle_quota(
                        session,
                        user_id=admitted_user_id,
                        resource="video",
                        idempotency_key=quota_key,
                    )
            job.status = "failed"
            job.error_log = "Project or exportable frames no longer exist"
            job.failure_retryable = False
            await session.commit()
            return None
        if job.status == "rendering":
            await session.execute(
                update(ExportJobAttempt)
                .where(
                    ExportJobAttempt.job_id == job.id,
                    ExportJobAttempt.status == "rendering",
                )
                .values(
                    status="lease_expired",
                    finished_at=now,
                    error_class="lease_expired",
                )
            )
        job.status = "rendering"
        job.attempt_count = (job.attempt_count or 0) + 1
        job.worker_id = WORKER_ID
        job.next_attempt_at = None
        job.lease_expires_at = now + timedelta(seconds=settings.manim_timeout_seconds + 120)
        attempt_id = uuid.uuid4()
        session.add(
            ExportJobAttempt(
                id=attempt_id,
                job_id=job.id,
                attempt_no=job.attempt_count,
                worker_id=WORKER_ID,
                status="rendering",
                heartbeat_at=now,
            )
        )
        await session.commit()
        return {
            "job_id": str(job.id),
            "owner_id": owner_id,
            "attempt_id": str(attempt_id),
            "attempt_no": job.attempt_count,
            "dsl": dsl,
            "source_version_id": (
                str(source_version_id)
                if isinstance(source_version_id, uuid.UUID)
                else None
            ),
            "config": dict(job.config or {}),
        }


async def renew_export_lease(job_id: str) -> bool:
    """Extend a lease only while this worker still owns a rendering job."""
    from db.database import async_session_factory
    from db.models import ExportJobAttempt, ExportJobModel

    settings = get_settings()
    lease_until = datetime.now(timezone.utc) + timedelta(
        seconds=settings.manim_timeout_seconds + 120
    )
    async with async_session_factory() as session:
        result = await session.execute(
            update(ExportJobModel)
            .where(
                ExportJobModel.id == uuid.UUID(job_id),
                ExportJobModel.status == "rendering",
                ExportJobModel.worker_id == WORKER_ID,
            )
            .values(lease_expires_at=lease_until)
        )
        await session.execute(
            update(ExportJobAttempt)
            .where(
                ExportJobAttempt.job_id == uuid.UUID(job_id),
                ExportJobAttempt.status == "rendering",
                ExportJobAttempt.worker_id == WORKER_ID,
            )
            .values(heartbeat_at=datetime.now(timezone.utc))
        )
        await session.commit()
        return bool(result.rowcount)


async def _maintain_export_lease(
    job_id: str,
    stop: asyncio.Event,
) -> bool:
    """Return True when ownership is lost, including an API cancellation."""
    settings = get_settings()
    while not stop.is_set():
        try:
            await asyncio.wait_for(
                stop.wait(), timeout=settings.export_worker_heartbeat_seconds
            )
            return False
        except TimeoutError:
            if not await renew_export_lease(job_id):
                logger.info("export lease lost or cancelled: job=%s", job_id)
                return True
    return False


async def run_claimed_export(job: dict[str, Any]) -> None:
    """Run one claimed job while renewing ownership and honoring cancellation."""
    from api.export import _fallback_export
    settings = get_settings()
    credentials = None
    llm_limits = None
    heartbeat_stop = asyncio.Event()
    render_task = None
    heartbeat_task = None
    try:
        # An optional creative Manim director is still a provider call. Resolve
        # the exact credential version captured at enqueue time inside the
        # trusted worker; the render sandbox never receives this value.
        from services.provider_credentials import CredentialReferenceUnavailableError
        credential_ref = (job.get("config") or {}).get("credential_ref")
        if credential_ref or (
            getattr(settings, "byok_required", False)
            and getattr(settings, "manim_script_mode", "deterministic") == "llm"
        ):
            owner_id = job.get("owner_id")
            if not owner_id:
                raise CredentialReferenceUnavailableError(
                    "A user-owned credential is required for LLM video scripting"
                )
            from db.database import async_session_factory
            from services.provider_credentials import resolve_credential_reference

            async with async_session_factory() as session:
                owner_uuid = uuid.UUID(str(owner_id))
                credentials = await resolve_credential_reference(
                    session, owner_uuid, credential_ref
                )
                from services.quota import resolve_user_llm_limits
                llm_limits = await resolve_user_llm_limits(session, owner_uuid)
                await session.commit()

        render_task = asyncio.create_task(
            _fallback_export(
                job["job_id"], job["dsl"], job["config"], credentials, llm_limits
            )
        )
        heartbeat_task = asyncio.create_task(
            _maintain_export_lease(job["job_id"], heartbeat_stop)
        )
        done, _ = await asyncio.wait(
            {render_task, heartbeat_task}, return_when=asyncio.FIRST_COMPLETED
        )
        if heartbeat_task in done and heartbeat_task.result():
            render_task.cancel()
            await asyncio.gather(render_task, return_exceptions=True)
            return
        await render_task
        await schedule_export_retry(job["job_id"], int(job.get("attempt_no", 1)))
    except asyncio.CancelledError:
        if render_task is not None:
            render_task.cancel()
            await asyncio.gather(render_task, return_exceptions=True)
        raise
    except Exception as exc:
        from api.export import _update_db_export_status
        from services.redaction import public_failure_message
        from services.provider_credentials import CredentialReferenceUnavailableError

        attempt_no = int(job.get("attempt_no", 1))
        # A revoked/rotated credential is a permanent queued-job failure; do
        # not retry it three times and do not ever fall back to a platform key.
        final_failure = (
            attempt_no >= settings.export_worker_max_attempts
            or isinstance(exc, CredentialReferenceUnavailableError)
        )
        await _update_db_export_status(
            job["job_id"],
            "failed",
            error_log=public_failure_message("export"),
            retryable_failure=not final_failure,
        )
        await schedule_export_retry(job["job_id"], attempt_no)
        raise
    finally:
        heartbeat_stop.set()
        if heartbeat_task is not None:
            await asyncio.gather(heartbeat_task, return_exceptions=True)
        # Drop the decrypted tuple as soon as the render attempt is over; the
        # no-network sandbox never receives it and cannot access KMS.
        credentials = None


def export_retry_delay_seconds(attempt_no: int) -> float:
    """Return capped exponential backoff with bounded positive jitter."""
    settings = get_settings()
    base = min(
        settings.export_retry_base_seconds * (2 ** max(attempt_no - 1, 0)),
        settings.export_retry_max_seconds,
    )
    return min(base + random.uniform(0, base * 0.2), settings.export_retry_max_seconds)


async def schedule_export_retry(job_id: str, attempt_no: int) -> bool:
    """Requeue the just-failed attempt without reviving terminal/cancelled jobs."""
    from db.database import async_session_factory
    from db.models import ExportJobAttempt, ExportJobModel

    settings = get_settings()
    if attempt_no >= settings.export_worker_max_attempts:
        return False
    now = datetime.now(timezone.utc)
    async with async_session_factory() as session:
        job = await session.get(ExportJobModel, uuid.UUID(job_id))
        if (
            job is None
            or job.status != "failed"
            or job.attempt_count != attempt_no
            or job.failure_retryable is False
        ):
            return False
        job.status = "queued"
        job.error_log = None
        job.completed_at = None
        job.next_attempt_at = now + timedelta(
            seconds=export_retry_delay_seconds(attempt_no)
        )
        await session.execute(
            update(ExportJobAttempt)
            .where(
                ExportJobAttempt.job_id == job.id,
                ExportJobAttempt.attempt_no == attempt_no,
                ExportJobAttempt.status == "failed",
            )
            .values(status="retry_scheduled", error_class="export_failed")
        )
        await session.commit()
        try:
            import redis

            from api.export import _try_update_redis_status

            client = redis.from_url(settings.redis_url, decode_responses=True)
            await asyncio.to_thread(
                _try_update_redis_status, client, job_id, "queued", progress=0
            )
        except Exception:
            logger.warning("export retry Redis sync failed: job=%s", job_id)
        logger.info(
            "export retry scheduled: job=%s attempt=%d next=%s",
            job_id,
            attempt_no,
            job.next_attempt_at.isoformat(),
        )
        return True


async def run_worker(stop_event: asyncio.Event | None = None) -> None:
    settings = get_settings()
    if settings.manim_execution_mode != "worker":
        raise RuntimeError("export worker requires MANIM_EXECUTION_MODE=worker")
    stop = stop_event or asyncio.Event()
    logger.info("export worker started")
    while not stop.is_set():
        try:
            job = await claim_export_job()
            if job is None:
                try:
                    await asyncio.wait_for(stop.wait(), timeout=settings.export_worker_poll_seconds)
                except TimeoutError:
                    pass
                continue
            await run_claimed_export(job)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("export worker iteration failed")
            try:
                await asyncio.wait_for(stop.wait(), timeout=settings.export_worker_poll_seconds)
            except TimeoutError:
                pass


def main() -> None:
    stop = asyncio.Event()

    async def serve() -> None:
        loop = asyncio.get_running_loop()
        for signame in ("SIGINT", "SIGTERM"):
            sig = getattr(signal, signame, None)
            if sig is not None:
                try:
                    loop.add_signal_handler(sig, stop.set)
                except NotImplementedError:
                    pass
        await run_worker(stop)

    asyncio.run(serve())


if __name__ == "__main__":
    main()
