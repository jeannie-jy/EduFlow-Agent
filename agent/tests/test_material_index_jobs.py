"""Consent, owner scope, and durable index job contracts."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


def _material(owner_id, *, library=True, suffix=".md"):
    return SimpleNamespace(
        id=uuid.uuid4(), owner_id=owner_id, is_library=library,
        stored_filename="source" + suffix, original_filename="课程" + suffix,
    )


@pytest.mark.asyncio
async def test_index_queue_requires_owner_and_opt_in_and_never_embeds():
    from api.materials import queue_material_index
    from db.models import BackgroundJob

    owner = SimpleNamespace(id=uuid.uuid4(), role="teacher")
    material = _material(owner.id)
    session = MagicMock()
    session.get = AsyncMock(return_value=material)
    session.scalar = AsyncMock(return_value=None)
    session.flush = AsyncMock()

    result = await queue_material_index(str(material.id), session, owner, owner)
    job = session.add.call_args.args[0]
    assert isinstance(job, BackgroundJob)
    assert job.kind == "material_index"
    assert job.owner_id == owner.id
    assert job.payload == {"material_id": str(material.id), "allow_embedding": False}
    assert result["status"] == "queued"

    session.add.reset_mock()
    material.owner_id = uuid.uuid4()
    with pytest.raises(HTTPException) as denied:
        await queue_material_index(str(material.id), session, owner, owner)
    assert denied.value.status_code == 404
    session.add.assert_not_called()

    material.owner_id = owner.id
    material.is_library = False
    with pytest.raises(HTTPException) as not_opted_in:
        await queue_material_index(str(material.id), session, owner, owner)
    assert not_opted_in.value.status_code == 404


@pytest.mark.asyncio
async def test_index_retry_only_resets_failed_owned_job():
    from api.materials import retry_material_index
    from db.models import BackgroundJob

    owner = SimpleNamespace(id=uuid.uuid4(), role="teacher")
    material = _material(owner.id)
    job = SimpleNamespace(
        id=uuid.uuid4(), status="failed", attempt_count=3,
        error_class="material_ocr_required", completed_at=object(), next_attempt_at=object(),
    )
    session = MagicMock()
    session.get = AsyncMock(return_value=material)
    session.scalar = AsyncMock(return_value=job)
    session.flush = AsyncMock()
    result = await retry_material_index(str(material.id), session, owner, owner)
    assert result["status"] == "queued"
    retry = session.add.call_args.args[0]
    assert isinstance(retry, BackgroundJob)
    assert retry.id != job.id and retry.payload["allow_embedding"] is False
    assert job.status == "failed" and job.attempt_count == 3
    assert job.error_class == "material_ocr_required"
    job.status = "running"
    with pytest.raises(HTTPException) as conflict:
        await retry_material_index(str(material.id), session, owner, owner)
    assert conflict.value.status_code == 409


@pytest.mark.asyncio
async def test_worker_rejects_paid_or_changed_owner_before_copy():
    from services.task_worker import PermanentTaskError, _execute_material_index

    owner_id = uuid.uuid4()
    material = _material(uuid.uuid4())
    session = MagicMock()
    session.get = AsyncMock(return_value=material)
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=session)
    context.__aexit__ = AsyncMock(return_value=None)
    job = {
        "job_id": str(uuid.uuid4()), "owner_id": str(owner_id), "attempt_no": 1,
        "payload": {"material_id": str(material.id), "allow_embedding": False},
    }
    with patch("db.database.async_session_factory", return_value=context), patch(
        "api.materials._copy_material_to", new_callable=AsyncMock
    ) as copier:
        with pytest.raises(PermanentTaskError, match="no longer belongs"):
            await _execute_material_index(job)
        copier.assert_not_awaited()
        job["payload"]["allow_embedding"] = True
        with pytest.raises(PermanentTaskError, match="Paid embedding"):
            await _execute_material_index(job)
        copier.assert_not_awaited()
