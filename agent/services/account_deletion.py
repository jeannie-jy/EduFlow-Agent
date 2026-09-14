"""Due account deletion processor shared by the scheduler and maintenance CLI."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import delete, select

logger = logging.getLogger(__name__)


async def _purge_runtime_state(project_ids: list[str], export_job_ids: list[str], feedback_job_ids: list[str]) -> None:
    """Remove non-relational runtime state that is not covered by FK cascades."""
    failures: list[tuple[str, Exception]] = []

    # Export progress keys contain no prompt or credential, but retaining them
    # after account deletion would still expose a stale artifact pointer.
    try:
        from api.export import _get_redis

        client = await _get_redis()
        if client is None and export_job_ids:
            raise RuntimeError("Redis client is unavailable")
        if client is not None:
            for job_id in export_job_ids:
                try:
                    await asyncio.to_thread(client.delete, f"manim:job:{job_id}")
                except Exception as exc:  # noqa: BLE001 - external Redis client errors vary
                    failures.append(("redis", exc))
    except Exception as exc:  # noqa: BLE001 - optional Redis initialization errors vary
        failures.append(("redis", exc))

    # LangGraph's Postgres saver owns checkpoint tables outside our ORM.  Use
    # its supported deletion API when the production saver is active; the
    # in-memory development saver simply has no async deletion method.
    try:
        from agents.graph import get_graph_async

        graph = await get_graph_async()
        saver = getattr(graph, "checkpointer", None)
        delete_thread = getattr(saver, "adelete_thread", None)
        if delete_thread is not None:
            for thread_id in [*project_ids, *feedback_job_ids]:
                try:
                    await delete_thread(thread_id)
                except Exception as exc:  # noqa: BLE001 - checkpointer backends vary
                    failures.append(("checkpoint", exc))
    except Exception as exc:  # noqa: BLE001 - optional graph backends vary
        failures.append(("checkpoint", exc))

    if failures:
        # Keep the relational deletion request intact. The maintenance worker
        # will retry the complete, idempotent purge on its next pass rather
        # than orphaning runtime data after the user row has disappeared.
        for subsystem, exc in failures:
            logger.warning(
                "account runtime cleanup failed: subsystem=%s error=%s",
                subsystem,
                type(exc).__name__,
            )
        raise RuntimeError("Account runtime cleanup is incomplete")


async def process_due_deletions() -> int:
    from db.database import async_session_factory
    from db.models import (
        AccountDeletionRequest,
        BackgroundJob,
        ExportJobModel,
        Material,
        Project,
        User,
    )
    from services.artifact_store import get_artifact_store

    deleted = 0
    async with async_session_factory() as session:
        requests = list((await session.scalars(
            select(AccountDeletionRequest)
            .where(AccountDeletionRequest.execute_after <= datetime.now(timezone.utc))
            .with_for_update(skip_locked=True)
        )).all())
        store = get_artifact_store()
        for request in requests:
            materials = list((await session.scalars(
                select(Material).where(Material.owner_id == request.user_id)
            )).all())
            projects = list((await session.scalars(
                select(Project).where(Project.owner_id == str(request.user_id))
            )).all())
            jobs = list((await session.scalars(
                select(ExportJobModel).where(
                    ExportJobModel.project_id.in_([project.id for project in projects])
                )
            )).all()) if projects else []
            background_jobs = list((await session.scalars(
                select(BackgroundJob).where(
                    BackgroundJob.owner_id == request.user_id,
                    BackgroundJob.project_id.in_([project.id for project in projects]),
                )
            )).all()) if projects else []
            await _purge_runtime_state(
                [str(project.id) for project in projects],
                [str(job.id) for job in jobs],
                [f"feedback:{job.id}" for job in background_jobs if job.kind == "feedback_reflection"],
            )
            for material in materials:
                if material.storage_key:
                    await store.delete(material.storage_key)
            for job in jobs:
                for artifact in job.artifacts or []:
                    if isinstance(artifact, dict) and artifact.get("storage_key"):
                        await store.delete(str(artifact["storage_key"]))
            await session.execute(delete(Project).where(Project.owner_id == str(request.user_id)))
            await session.execute(delete(User).where(User.id == request.user_id))
            deleted += 1
        await session.commit()
    return deleted
