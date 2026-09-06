"""Security gates for generated-code execution."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from schema.project import ExportManimRequest


def test_export_job_source_version_is_a_database_reference():
    from db.models import ExportJobModel

    column = ExportJobModel.__table__.columns["source_version_id"]
    targets = {foreign_key.target_fullname for foreign_key in column.foreign_keys}

    assert targets == {"project_versions.id"}
    assert column.nullable  # legacy jobs remain claimable after migration


@pytest.mark.asyncio
async def test_manim_export_is_disabled_before_database_access_by_default():
    from api.export import create_export_job

    settings = MagicMock(manim_execution_mode="disabled")
    session = MagicMock()
    with patch("api.export.get_settings", return_value=settings):
        with pytest.raises(HTTPException) as exc:
            await create_export_job(
                "00000000-0000-0000-0000-000000000001",
                MagicMock(),
                session,
            )
    assert exc.value.status_code == 503
    assert session.get.call_count == 0


@pytest.mark.asyncio
async def test_queue_mode_persists_job_without_starting_api_background_task():
    from api.export import create_export_job

    project = MagicMock(dsl_snapshot={"frames": [{"frame_id": "f1"}]})
    session = MagicMock()
    session.get = AsyncMock(return_value=project)
    frame_result = MagicMock()
    frame_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=frame_result)
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    settings = MagicMock(manim_execution_mode="queue")
    source_version_id = uuid.uuid4()
    with (
        patch("api.export.get_settings", return_value=settings),
        patch("api.export.asyncio.create_task") as create_task,
        patch(
            "api.versions.save_version",
            new=AsyncMock(
                return_value={"id": str(source_version_id), "version": 3}
            ),
        ) as save_version,
    ):
        result = await create_export_job(
            str(uuid.uuid4()), ExportManimRequest(), session
        )

    assert result["status"] == "queued"
    assert uuid.UUID(result["job_id"])
    assert result["source_version_id"] == str(source_version_id)
    assert session.add.call_count == 2  # export job + append-only audit event
    export_job = session.add.call_args_list[0].args[0]
    assert export_job.source_version_id == source_version_id
    save_version.assert_awaited_once()
    session.flush.assert_awaited_once()
    session.commit.assert_awaited_once()
    create_task.assert_not_called()


@pytest.mark.asyncio
async def test_api_rejects_worker_mode_to_keep_execution_roles_separate():
    from api.export import create_export_job

    session = MagicMock()
    with patch(
        "api.export.get_settings",
        return_value=MagicMock(manim_execution_mode="worker"),
    ):
        with pytest.raises(HTTPException) as exc:
            await create_export_job(str(uuid.uuid4()), ExportManimRequest(), session)

    assert exc.value.status_code == 503
    assert session.get.call_count == 0


@pytest.mark.asyncio
async def test_idempotency_key_returns_existing_job_without_duplicate_insert():
    from api.export import create_export_job

    existing = MagicMock(id=uuid.uuid4(), status="rendering")
    session = MagicMock()
    session.get = AsyncMock(
        return_value=MagicMock(dsl_snapshot={"frames": [{"frame_id": "f1"}]})
    )
    session.scalar = AsyncMock(return_value=existing)

    with patch(
        "api.export.get_settings",
        return_value=MagicMock(manim_execution_mode="queue"),
    ):
        result = await create_export_job(
            str(uuid.uuid4()),
            ExportManimRequest(),
            session,
            idempotency_key=" retry-safe-key ",
        )

    assert result == {
        "job_id": str(existing.id),
        "status": "rendering",
        "source_version_id": None,
    }
    session.add.assert_not_called()
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_owner_can_cancel_running_export_idempotently():
    from api.export import cancel_export_job

    job_id = str(uuid.uuid4())
    job = MagicMock(status="rendering")
    session = MagicMock()
    session.scalar = AsyncMock(return_value=job)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    with patch("api.export._get_redis", new=AsyncMock(return_value=None)):
        result = await cancel_export_job(
            job_id,
            session,
            MagicMock(id="owner-id"),
        )

    assert result == {"job_id": job_id, "status": "cancelled"}
    assert job.status == "cancelled"
    assert job.worker_id is None
    assert job.lease_expires_at is None
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_worker_completion_cannot_overwrite_cancelled_job():
    from api.export import _update_db_export_status

    job = MagicMock(status="cancelled")
    session = MagicMock()
    session.get = AsyncMock(return_value=job)
    session.commit = AsyncMock()
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=session)
    context.__aexit__ = AsyncMock(return_value=None)
    with patch("db.database.async_session_factory", return_value=context):
        persisted = await _update_db_export_status(
            str(uuid.uuid4()), "completed", artifacts=[{"filename": "late.mp4"}]
        )

    assert persisted is False
    assert job.status == "cancelled"
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_published_artifacts_are_deleted_when_job_loses_terminal_write(tmp_path):
    from api.export import _publish_and_persist_export_artifacts

    published = [
        {"filename": "lesson.mp4", "storage_key": "exports/job/lesson.mp4"},
        {"filename": "main.py", "storage_key": "exports/job/main.py"},
    ]
    store = MagicMock(delete=AsyncMock())
    with (
        patch(
            "api.export._publish_export_artifacts",
            new=AsyncMock(return_value=published),
        ),
        patch("api.export._update_db_export_status", new=AsyncMock(return_value=False)),
        patch("services.artifact_store.get_artifact_store", return_value=store),
    ):
        persisted, result = await _publish_and_persist_export_artifacts(
            tmp_path,
            "job",
            [],
        )

    assert persisted is False
    assert result == published
    assert [call.args[0] for call in store.delete.await_args_list] == [
        "exports/job/lesson.mp4",
        "exports/job/main.py",
    ]


@pytest.mark.asyncio
async def test_published_artifacts_are_deleted_when_database_write_raises(tmp_path):
    from api.export import _publish_and_persist_export_artifacts

    published = [{"filename": "lesson.mp4", "storage_key": "exports/job/lesson.mp4"}]
    store = MagicMock(delete=AsyncMock())
    with (
        patch(
            "api.export._publish_export_artifacts",
            new=AsyncMock(return_value=published),
        ),
        patch(
            "api.export._update_db_export_status",
            new=AsyncMock(side_effect=RuntimeError("commit failed")),
        ),
        patch("services.artifact_store.get_artifact_store", return_value=store),
        pytest.raises(RuntimeError, match="commit failed"),
    ):
        await _publish_and_persist_export_artifacts(tmp_path, "job", [])

    store.delete.assert_awaited_once_with("exports/job/lesson.mp4")
