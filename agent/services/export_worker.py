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
        terminal_expired = select(ExportJobModel.id).where(
            ExportJobModel.status == "rendering",
            ExportJobModel.lease_expires_at < now,
            ExportJobModel.attempt_count >= settings.export_worker_max_attempts,
        )
        await session.execute(
            update(ExportJobAttempt)
            .where(
                ExportJobAttempt.job_id.in_(terminal_expired),
                ExportJobAttempt.status == "rendering",
            )
            .values(
                status="failed",
                finished_at=now,
                error_class="lease_expired",
            )
        )
        await session.execute(
            update(ExportJobModel)
            .where(
                ExportJobModel.status == "rendering",
                ExportJobModel.lease_expires_at < now,
                ExportJobModel.attempt_count >= settings.export_worker_max_attempts,
            )
            .values(
                status="failed",
                error_log="Export worker lease expired after maximum attempts",
                worker_id=None,
                lease_expires_at=None,
                next_attempt_at=None,
                completed_at=now,
            )
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
            project = await session.get(Project, job.project_id)
            dsl = await load_canonical_project_dsl(project, session) if project else None
        if dsl is None:
            job.status = "failed"
            job.error_log = "Project or exportable frames no longer exist"
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

    heartbeat_stop = asyncio.Event()
    render_task = asyncio.create_task(
        _fallback_export(job["job_id"], job["dsl"], job["config"])
    )
    heartbeat_task = asyncio.create_task(
        _maintain_export_lease(job["job_id"], heartbeat_stop)
    )
    try:
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
        render_task.cancel()
        await asyncio.gather(render_task, return_exceptions=True)
        raise
    except Exception:
        from api.export import _update_db_export_status
        from services.redaction import public_failure_message

        await _update_db_export_status(
            job["job_id"],
            "failed",
            error_log=public_failure_message("export"),
        )
        await schedule_export_retry(job["job_id"], int(job.get("attempt_no", 1)))
        raise
    finally:
        heartbeat_stop.set()
        await asyncio.gather(heartbeat_task, return_exceptions=True)


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
