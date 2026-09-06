"""Durable worker for asynchronous Agent tasks such as feedback reflection."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import random
import signal
import socket
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import and_, or_, select, update

from config import get_settings

logger = logging.getLogger(__name__)
TASK_WORKER_ID = os.getenv("EDUFLOW_TASK_WORKER_ID") or (
    f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
)


class PermanentTaskError(RuntimeError):
    """A task cannot succeed by retrying the same persisted input."""


def task_retry_delay_seconds(attempt_no: int) -> float:
    settings = get_settings()
    base = min(
        settings.task_retry_base_seconds * (2 ** max(attempt_no - 1, 0)),
        settings.task_retry_max_seconds,
    )
    return min(base + random.uniform(0, base * 0.2), settings.task_retry_max_seconds)


async def claim_background_job() -> dict[str, Any] | None:
    from db.database import async_session_factory
    from db.models import BackgroundJob, BackgroundJobAttempt

    settings = get_settings()
    now = datetime.now(timezone.utc)
    async with async_session_factory() as session:
        terminal_ids = select(BackgroundJob.id).where(
            BackgroundJob.status == "running",
            BackgroundJob.lease_expires_at < now,
            BackgroundJob.attempt_count >= settings.task_worker_max_attempts,
        )
        await session.execute(
            update(BackgroundJobAttempt)
            .where(
                BackgroundJobAttempt.job_id.in_(terminal_ids),
                BackgroundJobAttempt.status == "running",
            )
            .values(
                status="failed",
                error_class="lease_expired",
                finished_at=now,
            )
        )
        await session.execute(
            update(BackgroundJob)
            .where(
                BackgroundJob.status == "running",
                BackgroundJob.lease_expires_at < now,
                BackgroundJob.attempt_count >= settings.task_worker_max_attempts,
            )
            .values(
                status="failed",
                error_class="lease_expired",
                worker_id=None,
                lease_expires_at=None,
                completed_at=now,
            )
        )
        result = await session.execute(
            select(BackgroundJob)
            .where(
                BackgroundJob.attempt_count < settings.task_worker_max_attempts,
                or_(
                    and_(
                        BackgroundJob.status == "queued",
                        or_(
                            BackgroundJob.next_attempt_at.is_(None),
                            BackgroundJob.next_attempt_at <= now,
                        ),
                    ),
                    and_(
                        BackgroundJob.status == "running",
                        BackgroundJob.lease_expires_at < now,
                    ),
                ),
            )
            .order_by(BackgroundJob.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        job = result.scalar_one_or_none()
        if job is None:
            await session.commit()
            return None
        if job.status == "running":
            await session.execute(
                update(BackgroundJobAttempt)
                .where(
                    BackgroundJobAttempt.job_id == job.id,
                    BackgroundJobAttempt.status == "running",
                )
                .values(
                    status="lease_expired",
                    error_class="lease_expired",
                    finished_at=now,
                )
            )
        job.status = "running"
        job.attempt_count = (job.attempt_count or 0) + 1
        job.worker_id = TASK_WORKER_ID
        job.lease_expires_at = now + timedelta(
            seconds=settings.task_worker_lease_seconds
        )
        job.next_attempt_at = None
        attempt_id = uuid.uuid4()
        session.add(
            BackgroundJobAttempt(
                id=attempt_id,
                job_id=job.id,
                attempt_no=job.attempt_count,
                worker_id=TASK_WORKER_ID,
                status="running",
                heartbeat_at=now,
            )
        )
        await session.commit()
        return {
            "job_id": str(job.id),
            "project_id": str(job.project_id) if job.project_id else None,
            "owner_id": str(job.owner_id) if getattr(job, "owner_id", None) else None,
            "kind": job.kind,
            "payload": dict(job.payload or {}),
            "attempt_no": job.attempt_count,
        }


async def renew_background_lease(job_id: str) -> bool:
    from db.database import async_session_factory
    from db.models import BackgroundJob, BackgroundJobAttempt

    settings = get_settings()
    now = datetime.now(timezone.utc)
    async with async_session_factory() as session:
        result = await session.execute(
            update(BackgroundJob)
            .where(
                BackgroundJob.id == uuid.UUID(job_id),
                BackgroundJob.status == "running",
                BackgroundJob.worker_id == TASK_WORKER_ID,
            )
            .values(
                lease_expires_at=now
                + timedelta(seconds=settings.task_worker_lease_seconds)
            )
        )
        await session.execute(
            update(BackgroundJobAttempt)
            .where(
                BackgroundJobAttempt.job_id == uuid.UUID(job_id),
                BackgroundJobAttempt.status == "running",
                BackgroundJobAttempt.worker_id == TASK_WORKER_ID,
            )
            .values(heartbeat_at=now)
        )
        await session.commit()
        return bool(result.rowcount)


async def _maintain_task_lease(job_id: str, stop: asyncio.Event) -> bool:
    settings = get_settings()
    while not stop.is_set():
        try:
            await asyncio.wait_for(
                stop.wait(), timeout=settings.task_worker_heartbeat_seconds
            )
            return False
        except TimeoutError:
            if not await renew_background_lease(job_id):
                return True
    return False


async def _execute_feedback_reflection(job: dict[str, Any]) -> None:
    from agents.graph import get_graph_async
    from agents.state import AgentState
    from api.versions import save_version
    from db.database import async_session_factory
    from db.models import BackgroundJob, BackgroundJobAttempt, Feedback, Project
    from services.generate_service import _workflow_llm_budget
    from services.project_persistence import (
        load_canonical_project_dsl,
        merge_dsl_snapshot,
        persist_frames_to_table,
    )

    try:
        feedback_id = uuid.UUID(str(job["payload"].get("feedback_id", "")))
        project_id = uuid.UUID(job["project_id"])
    except (ValueError, TypeError, AttributeError) as exc:
        raise PermanentTaskError("Task identifiers are invalid") from exc
    async with async_session_factory() as session:
        project = await session.get(Project, project_id)
        feedback = await session.get(Feedback, feedback_id)
        if project is None or feedback is None:
            raise PermanentTaskError("Reflection input no longer exists")
        dsl = await load_canonical_project_dsl(project, session)
        if dsl is None:
            raise PermanentTaskError("Project has no generated DSL")
        feedback_data = {
            "frame_id": job["payload"].get("frame_id"),
            "type": feedback.type,
            "content": feedback.content,
            "rating": feedback.rating,
        }

    existing_frame_ids = {
        str(frame.get("frame_id"))
        for frame in dsl.get("frames", [])
        if isinstance(frame, dict) and frame.get("frame_id")
    }
    locked_frame_ids = {
        str(frame.get("frame_id"))
        for frame in dsl.get("frames", [])
        if isinstance(frame, dict) and frame.get("frame_id") and frame.get("is_locked")
    }
    target_frame_id = feedback_data.get("frame_id")
    if target_frame_id:
        if target_frame_id not in existing_frame_ids:
            raise PermanentTaskError("Feedback target frame no longer exists")
        locked_frame_ids.update(existing_frame_ids - {target_frame_id})

    state: AgentState = {
        "workflow_entry": "reflection",
        "project_id": str(project_id),
        "dsl": dsl,
        "user_feedback": feedback_data,
        "quality_report": {"overall_score": 0.5, "is_blocking": True},
        "reflection_count": 0,
        "revision_history": [],
        "locked_frame_ids": sorted(locked_frame_ids),
        "status": "reviewing",
    }
    graph = await get_graph_async()
    graph_config = {"configurable": {"thread_id": f"feedback:{job['job_id']}"}}
    from services.workflow_trace import invoke_graph_traced

    with _workflow_llm_budget():
        result = await invoke_graph_traced(
            graph,
            state,
            graph_config,
            project_id=str(project_id),
            entrypoint="reflection",
        )
    revised_dsl = result.get("dsl") or dsl

    now = datetime.now(timezone.utc)
    async with async_session_factory() as session:
        queued_job = await session.get(BackgroundJob, uuid.UUID(job["job_id"]))
        project = await session.get(Project, project_id)
        feedback = await session.get(Feedback, feedback_id)
        if (
            queued_job is None
            or queued_job.status != "running"
            or queued_job.worker_id != TASK_WORKER_ID
            or project is None
            or feedback is None
        ):
            raise PermanentTaskError("Reflection task lost ownership or input")
        project.dsl_snapshot = merge_dsl_snapshot(
            project.dsl_snapshot,
            revised_dsl,
            quality_report=result.get("quality_report"),
        )
        await persist_frames_to_table(
            str(project_id), revised_dsl.get("frames", []), session
        )
        await save_version(
            str(project_id),
            project.dsl_snapshot,
            "反馈触发的 Reflection",
            session,
        )
        feedback.resolved = True
        queued_job.status = "completed"
        queued_job.worker_id = None
        queued_job.lease_expires_at = None
        queued_job.completed_at = now
        await session.execute(
            update(BackgroundJobAttempt)
            .where(
                BackgroundJobAttempt.job_id == queued_job.id,
                BackgroundJobAttempt.status == "running",
            )
            .values(status="completed", finished_at=now)
        )
        await session.commit()


async def _execute_material_parse(job: dict[str, Any]) -> None:
    """Parse an object-store material outside the API process and commit atomically."""
    from api.materials import parse_material_record
    from db.database import async_session_factory
    from db.models import BackgroundJob, BackgroundJobAttempt, Material

    try:
        material_id = uuid.UUID(str(job["payload"].get("material_id", "")))
    except (ValueError, TypeError, AttributeError) as exc:
        raise PermanentTaskError("Material identifier is invalid") from exc

    async with async_session_factory() as session:
        material = await session.get(Material, material_id)
        if material is None:
            raise PermanentTaskError("Material no longer exists")
        expected_owner = job.get("owner_id")
        if expected_owner and str(material.owner_id) != expected_owner:
            raise PermanentTaskError("Material ownership changed")
    # Do not hold a database connection while downloading/parsing a potentially
    # large document. Production sends it to a credential-free no-network sidecar.
    if get_settings().material_parse_execution_mode == "sandbox":
        parsed = await _parse_material_via_sandbox(material, job)
    else:
        parsed = await parse_material_record(material)

    now = datetime.now(timezone.utc)
    async with async_session_factory() as session:
        queued_job = await session.get(BackgroundJob, uuid.UUID(job["job_id"]))
        material = await session.get(Material, material_id)
        if (
            queued_job is None
            or queued_job.status != "running"
            or queued_job.worker_id != TASK_WORKER_ID
            or queued_job.attempt_count != job["attempt_no"]
            or material is None
        ):
            raise PermanentTaskError("Material parse task lost ownership or input")
        material.parsed_result = parsed
        material.status = "parsed"
        queued_job.status = "completed"
        queued_job.worker_id = None
        queued_job.lease_expires_at = None
        queued_job.completed_at = now
        await session.execute(
            update(BackgroundJobAttempt)
            .where(
                BackgroundJobAttempt.job_id == queued_job.id,
                BackgroundJobAttempt.status == "running",
            )
            .values(status="completed", finished_at=now)
        )
        await session.commit()


async def _parse_material_via_sandbox(material, job: dict[str, Any]) -> dict:
    """Download, sign and exchange one parse request through a shared volume."""
    from api.materials import _copy_material_to, _validate_parsed_result

    settings = get_settings()
    root = settings.material_sandbox_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    suffix = Path(material.stored_filename).suffix.lower()
    attempt_id = uuid.uuid4().hex
    prefix = f"{job['job_id']}-{job['attempt_no']}-"
    with tempfile.TemporaryDirectory(prefix=prefix, dir=root) as temp_dir:
        job_dir = Path(temp_dir).resolve()
        if not job_dir.is_relative_to(root):
            raise PermanentTaskError("Material sandbox path escaped its root")
        source_path = job_dir / f"source{suffix}"
        await _copy_material_to(material, source_path)
        source_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()
        request_path = job_dir / "parse-request.json"
        request_tmp = job_dir / f".parse-request-{attempt_id}.tmp"
        result_path = job_dir / "parse-result.json"
        request_tmp.write_text(
            json.dumps(
                {
                    "attempt_id": attempt_id,
                    "source_name": source_path.name,
                    "source_sha256": source_sha256,
                }
            ),
            encoding="utf-8",
        )
        request_tmp.replace(request_path)

        deadline = (
            asyncio.get_running_loop().time() + settings.material_parse_timeout_seconds
        )
        while asyncio.get_running_loop().time() < deadline:
            if result_path.exists():
                try:
                    if (
                        result_path.stat().st_size
                        > settings.material_parse_result_max_bytes
                    ):
                        raise PermanentTaskError("Material sandbox result is oversized")
                    result = json.loads(result_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    result = None
                if isinstance(result, dict) and result.get("attempt_id") == attempt_id:
                    if result.get("status") == "completed" and isinstance(
                        result.get("parsed_result"), dict
                    ):
                        return _validate_parsed_result(result["parsed_result"])
                    if result.get("retryable") is False:
                        raise PermanentTaskError("Material sandbox rejected the input")
                    raise RuntimeError("Material sandbox failed to parse the input")
            await asyncio.sleep(min(settings.task_worker_poll_seconds, 1.0))
    raise TimeoutError("Material sandbox did not return a result before the deadline")


async def _mark_task_failure(
    job: dict[str, Any], *, error_class: str, retryable: bool
) -> None:
    from db.database import async_session_factory
    from db.models import BackgroundJob, BackgroundJobAttempt

    settings = get_settings()
    now = datetime.now(timezone.utc)
    async with async_session_factory() as session:
        queued_job = await session.get(BackgroundJob, uuid.UUID(job["job_id"]))
        if (
            queued_job is None
            or queued_job.status != "running"
            or queued_job.worker_id != TASK_WORKER_ID
            or queued_job.attempt_count != job["attempt_no"]
        ):
            return
        should_retry = (
            retryable and queued_job.attempt_count < settings.task_worker_max_attempts
        )
        queued_job.status = "queued" if should_retry else "failed"
        queued_job.error_class = error_class[:100]
        queued_job.worker_id = None
        queued_job.lease_expires_at = None
        queued_job.completed_at = None if should_retry else now
        queued_job.next_attempt_at = (
            now + timedelta(seconds=task_retry_delay_seconds(queued_job.attempt_count))
            if should_retry
            else None
        )
        if getattr(queued_job, "kind", None) == "material_parse" and not should_retry:
            from db.models import Material

            try:
                material_id = uuid.UUID(
                    str(job.get("payload", {}).get("material_id", ""))
                )
            except (ValueError, TypeError, AttributeError):
                material_id = None
            if material_id is not None:
                material = await session.get(Material, material_id)
                if material is not None:
                    material.status = "parse_failed"
        await session.execute(
            update(BackgroundJobAttempt)
            .where(
                BackgroundJobAttempt.job_id == queued_job.id,
                BackgroundJobAttempt.status == "running",
            )
            .values(
                status="retry_scheduled" if should_retry else "failed",
                error_class=error_class[:100],
                finished_at=now,
            )
        )
        await session.commit()


async def run_claimed_background_job(job: dict[str, Any]) -> None:
    stop = asyncio.Event()
    handlers = {
        "feedback_reflection": _execute_feedback_reflection,
        "material_parse": _execute_material_parse,
    }
    handler = handlers.get(job["kind"])
    if handler is None:
        await _mark_task_failure(
            job, error_class="unsupported_task_kind", retryable=False
        )
        return
    processing = asyncio.create_task(handler(job))
    heartbeat = asyncio.create_task(_maintain_task_lease(job["job_id"], stop))
    try:
        done, _ = await asyncio.wait(
            {processing, heartbeat}, return_when=asyncio.FIRST_COMPLETED
        )
        if heartbeat in done and heartbeat.result():
            processing.cancel()
            await asyncio.gather(processing, return_exceptions=True)
            return
        await processing
    except asyncio.CancelledError:
        processing.cancel()
        await asyncio.gather(processing, return_exceptions=True)
        raise
    except Exception as exc:
        retryable = not isinstance(exc, PermanentTaskError)
        await _mark_task_failure(
            job,
            error_class=type(exc).__name__,
            retryable=retryable,
        )
        logger.exception("background task failed: job=%s", job["job_id"])
    finally:
        stop.set()
        await asyncio.gather(heartbeat, return_exceptions=True)


async def run_worker(stop_event: asyncio.Event | None = None) -> None:
    settings = get_settings()
    stop = stop_event or asyncio.Event()
    logger.info("background Agent task worker started")
    while not stop.is_set():
        try:
            job = await claim_background_job()
            if job is not None:
                await run_claimed_background_job(job)
                continue
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("background task worker iteration failed")
        try:
            await asyncio.wait_for(
                stop.wait(), timeout=settings.task_worker_poll_seconds
            )
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
