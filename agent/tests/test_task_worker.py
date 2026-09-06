"""Durable background Agent task tests."""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml


def _context(session):
    value = MagicMock()
    value.__aenter__ = AsyncMock(return_value=session)
    value.__aexit__ = AsyncMock(return_value=None)
    return value


@pytest.mark.asyncio
async def test_feedback_reflection_is_enqueued_in_same_transaction():
    from api.feedback import submit_feedback
    from db.models import BackgroundJob, Feedback
    from schema.project import FeedbackRequest

    project_id = uuid.uuid4()
    project = SimpleNamespace(
        id=project_id, dsl_snapshot={"frames": [{"frame_id": "f1"}]}
    )
    query_result = MagicMock()
    query_result.first.return_value = (uuid.uuid4(),)
    session = MagicMock()
    session.get = AsyncMock(return_value=project)
    session.execute = AsyncMock(return_value=query_result)
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.add = MagicMock()

    result = await submit_feedback(
        str(project_id),
        FeedbackRequest(frame_id="f1", type="correction", content="这里不正确"),
        session,
    )

    added = [call.args[0] for call in session.add.call_args_list]
    assert any(isinstance(item, Feedback) for item in added)
    queued = next(item for item in added if isinstance(item, BackgroundJob))
    assert queued.kind == "feedback_reflection"
    assert queued.payload["frame_id"] == "f1"
    assert result["reflection_job_id"] == str(queued.id)
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_suggestion_persists_without_background_job():
    from api.feedback import submit_feedback
    from db.models import BackgroundJob
    from schema.project import FeedbackRequest

    project_id = uuid.uuid4()
    session = MagicMock()
    session.get = AsyncMock(
        return_value=SimpleNamespace(
            id=project_id, dsl_snapshot={"frames": [{"frame_id": "f1"}]}
        )
    )
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.add = MagicMock()

    result = await submit_feedback(
        str(project_id),
        FeedbackRequest(type="suggestion", content="可以增加例子"),
        session,
    )

    assert result["reflection_job_id"] is None
    assert not any(
        isinstance(call.args[0], BackgroundJob) for call in session.add.call_args_list
    )


@pytest.mark.asyncio
async def test_material_parse_endpoint_only_enqueues_durable_job():
    from api.materials import parse_material
    from db.models import BackgroundJob, Material

    material_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    material = Material(
        id=material_id,
        owner_id=owner_id,
        original_filename="lesson.md",
        stored_filename="uploaded.md",
        storage_key="materials/source.md",
        media_type="text/markdown",
        size_bytes=10,
        status="uploaded",
        expires_at=datetime.now(timezone.utc),
    )
    session = MagicMock()
    session.get = AsyncMock(return_value=material)
    session.scalar = AsyncMock(return_value=None)
    session.add = MagicMock()
    session.flush = AsyncMock()
    user = SimpleNamespace(id=owner_id)

    with patch("api.materials.parse_material_record", new=AsyncMock()) as parser:
        result = await parse_material(str(material_id), session, user, user)

    parser.assert_not_awaited()
    queued = next(
        call.args[0]
        for call in session.add.call_args_list
        if isinstance(call.args[0], BackgroundJob)
    )
    assert isinstance(queued, BackgroundJob)
    assert queued.kind == "material_parse"
    assert queued.project_id is None
    assert queued.owner_id == owner_id
    assert material.status == "parse_queued"
    assert result["job_id"] == str(queued.id)


@pytest.mark.asyncio
async def test_material_parse_endpoint_is_idempotent_while_queued():
    from api.materials import parse_material

    material_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    material = SimpleNamespace(
        id=material_id, owner_id=owner_id, status="parse_queued", parsed_result=None
    )
    queued = SimpleNamespace(id=uuid.uuid4(), status="queued")
    session = MagicMock()
    session.get = AsyncMock(return_value=material)
    session.scalar = AsyncMock(return_value=queued)
    session.add = MagicMock()
    user = SimpleNamespace(id=owner_id)

    result = await parse_material(str(material_id), session, user, user)

    session.add.assert_not_called()
    assert result["job_id"] == str(queued.id)


@pytest.mark.asyncio
async def test_material_worker_parses_and_commits_only_while_holding_lease():
    from services.task_worker import TASK_WORKER_ID, _execute_material_parse

    material_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    job_id = uuid.uuid4()
    read_material = SimpleNamespace(id=material_id, owner_id=owner_id)
    read_session = MagicMock()
    read_session.get = AsyncMock(return_value=read_material)
    queued_job = SimpleNamespace(
        id=job_id,
        status="running",
        worker_id=TASK_WORKER_ID,
        attempt_count=1,
        lease_expires_at=datetime.now(timezone.utc),
        completed_at=None,
    )
    write_material = SimpleNamespace(parsed_result=None, status="parse_queued")
    write_session = MagicMock()

    async def write_get(model, _identity):
        return queued_job if "BackgroundJob" in str(model) else write_material

    write_session.get = write_get
    write_session.execute = AsyncMock()
    write_session.commit = AsyncMock()
    parsed = {"topics": ["队列"], "raw_text": "先进先出"}

    with (
        patch(
            "db.database.async_session_factory",
            side_effect=[_context(read_session), _context(write_session)],
        ),
        patch(
            "api.materials.parse_material_record", new=AsyncMock(return_value=parsed)
        ),
    ):
        await _execute_material_parse(
            {
                "job_id": str(job_id),
                "project_id": None,
                "owner_id": str(owner_id),
                "kind": "material_parse",
                "payload": {"material_id": str(material_id)},
                "attempt_no": 1,
            }
        )

    assert write_material.parsed_result == parsed
    assert write_material.status == "parsed"
    assert queued_job.status == "completed"
    assert queued_job.worker_id is None
    write_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_material_worker_exchanges_signed_request_with_parser_sandbox(tmp_path):
    from services.task_worker import _parse_material_via_sandbox

    material = SimpleNamespace(stored_filename="lesson.md")
    job = {"job_id": str(uuid.uuid4()), "attempt_no": 1}
    settings = MagicMock(
        material_sandbox_dir=tmp_path,
        material_parse_timeout_seconds=1,
        material_parse_result_max_bytes=4096,
        task_worker_poll_seconds=0.001,
    )

    async def copy_material(_material, destination):
        destination.write_text("队列先进先出", encoding="utf-8")

    with (
        patch("services.task_worker.get_settings", return_value=settings),
        patch("api.materials._copy_material_to", new=copy_material),
    ):
        pending = asyncio.create_task(_parse_material_via_sandbox(material, job))
        request_path = None
        for _ in range(100):
            matches = list(tmp_path.glob("*/parse-request.json"))
            if matches:
                request_path = matches[0]
                break
            await asyncio.sleep(0.001)
        assert request_path is not None
        request = json.loads(request_path.read_text(encoding="utf-8"))
        source = request_path.parent / request["source_name"]
        assert (
            request["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
        )
        parsed = {"topics": ["队列"], "raw_text": "队列先进先出"}
        (request_path.parent / "parse-result.json").write_text(
            json.dumps(
                {
                    "attempt_id": request["attempt_id"],
                    "status": "completed",
                    "parsed_result": parsed,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        result = await pending

    assert result == parsed


@pytest.mark.asyncio
async def test_feedback_worker_runs_canonical_reflection_graph_and_commits_result():
    from services.task_worker import TASK_WORKER_ID, _execute_feedback_reflection

    project_id = uuid.uuid4()
    feedback_id = uuid.uuid4()
    job_id = uuid.uuid4()
    original = {
        "frames": [
            {"frame_id": "f1", "title": "old"},
            {"frame_id": "f2", "title": "preserve"},
        ]
    }
    project_read = SimpleNamespace(id=project_id, dsl_snapshot=original)
    feedback_read = SimpleNamespace(
        id=feedback_id, type="correction", content="fix", rating=None
    )
    read_session = MagicMock()

    async def read_get(model, identity):
        return feedback_read if "Feedback" in str(model) else project_read

    read_session.get = read_get
    frame_result = MagicMock()
    frame_result.scalars.return_value.all.return_value = []
    read_session.execute = AsyncMock(return_value=frame_result)

    queued_job = SimpleNamespace(
        id=job_id,
        status="running",
        worker_id=TASK_WORKER_ID,
        lease_expires_at=None,
        completed_at=None,
    )
    project_write = SimpleNamespace(id=project_id, dsl_snapshot=original)
    feedback_write = SimpleNamespace(resolved=False)
    write_session = MagicMock()

    async def write_get(model, identity):
        name = str(model)
        if "BackgroundJob" in name:
            return queued_job
        if "Feedback" in name:
            return feedback_write
        return project_write

    write_session.get = write_get
    write_session.execute = AsyncMock()
    write_session.commit = AsyncMock()

    graph = MagicMock()
    revised = {
        "frames": [
            {"frame_id": "f1", "title": "fixed"},
            {"frame_id": "f2", "title": "preserve"},
        ]
    }
    traced_invoke = AsyncMock(
        return_value={
            "dsl": revised,
            "quality_report": {"overall_score": 0.9},
        }
    )
    contexts = [_context(read_session), _context(write_session)]
    with (
        patch("db.database.async_session_factory", side_effect=contexts),
        patch("agents.graph.get_graph_async", new=AsyncMock(return_value=graph)),
        patch("services.workflow_trace.invoke_graph_traced", new=traced_invoke),
        patch(
            "services.generate_service._workflow_llm_budget", return_value=nullcontext()
        ),
        patch(
            "services.project_persistence.persist_frames_to_table", new=AsyncMock()
        ) as persist,
        patch("api.versions.save_version", new=AsyncMock()) as save,
    ):
        await _execute_feedback_reflection(
            {
                "job_id": str(job_id),
                "project_id": str(project_id),
                "kind": "feedback_reflection",
                "payload": {"feedback_id": str(feedback_id), "frame_id": "f1"},
                "attempt_no": 1,
            }
        )

    state = traced_invoke.await_args.args[1]
    assert state["workflow_entry"] == "reflection"
    assert state["user_feedback"]["frame_id"] == "f1"
    assert state["locked_frame_ids"] == ["f2"]
    assert traced_invoke.await_args.kwargs["entrypoint"] == "reflection"
    assert traced_invoke.await_args.kwargs["project_id"] == str(project_id)
    persist.assert_awaited_once()
    save.assert_awaited_once()
    assert project_write.dsl_snapshot["frames"][0]["title"] == "fixed"
    assert feedback_write.resolved is True
    assert queued_job.status == "completed"
    write_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_claim_records_durable_attempt_and_lease():
    from services.task_worker import TASK_WORKER_ID, claim_background_job

    job = SimpleNamespace(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        kind="feedback_reflection",
        payload={"feedback_id": str(uuid.uuid4())},
        status="queued",
        attempt_count=0,
        next_attempt_at=None,
    )
    selected = MagicMock()
    selected.scalar_one_or_none.return_value = job
    session = MagicMock()
    session.execute = AsyncMock(side_effect=[MagicMock(), MagicMock(), selected])
    session.add = MagicMock()
    session.commit = AsyncMock()
    settings = MagicMock(task_worker_max_attempts=3, task_worker_lease_seconds=300)

    with (
        patch("services.task_worker.get_settings", return_value=settings),
        patch("db.database.async_session_factory", return_value=_context(session)),
    ):
        claimed = await claim_background_job()

    assert claimed["attempt_no"] == 1
    assert job.status == "running"
    assert job.worker_id == TASK_WORKER_ID
    assert job.lease_expires_at > datetime.now(timezone.utc)
    session.add.assert_called_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_transient_task_failure_enters_retry_wait_with_backoff():
    from services.task_worker import TASK_WORKER_ID, _mark_task_failure

    job_id = uuid.uuid4()
    queued = SimpleNamespace(
        id=job_id,
        status="running",
        worker_id=TASK_WORKER_ID,
        attempt_count=1,
        error_class=None,
        lease_expires_at=datetime.now(timezone.utc),
        completed_at=None,
        next_attempt_at=None,
    )
    session = MagicMock()
    session.get = AsyncMock(return_value=queued)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    settings = MagicMock(task_worker_max_attempts=3)
    with (
        patch("services.task_worker.get_settings", return_value=settings),
        patch("services.task_worker.task_retry_delay_seconds", return_value=10),
        patch("db.database.async_session_factory", return_value=_context(session)),
    ):
        await _mark_task_failure(
            {"job_id": str(job_id), "attempt_no": 1},
            error_class="TimeoutError",
            retryable=True,
        )

    assert queued.status == "queued"
    assert queued.completed_at is None
    assert (
        9 <= (queued.next_attempt_at - datetime.now(timezone.utc)).total_seconds() <= 10
    )
    session.commit.assert_awaited_once()


def test_feedback_api_has_no_process_local_background_task():
    import ast

    source = (Path(__file__).resolve().parents[1] / "api" / "feedback.py").read_text(
        encoding="utf-8"
    )
    calls = [node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Call)]
    assert not any(
        isinstance(call.func, ast.Attribute) and call.func.attr == "create_task"
        for call in calls
    )
    assert "BackgroundJob(" in source


def test_compose_runs_hardened_durable_task_worker():
    compose = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / "docker-compose.yml").read_text(
            encoding="utf-8"
        )
    )
    worker = compose["services"]["task-worker"]
    assert worker["command"] == ["python", "-m", "services.task_worker"]
    assert worker["read_only"] is True
    assert worker["cap_drop"] == ["ALL"]
    assert "ports" not in worker


@pytest.mark.asyncio
async def test_background_job_status_is_owner_scoped():
    from fastapi import HTTPException

    from api.jobs import get_background_job

    current_user = SimpleNamespace(id=uuid.uuid4())
    session = MagicMock()
    session.scalar = AsyncMock(return_value=None)
    with pytest.raises(HTTPException) as caught:
        await get_background_job(str(uuid.uuid4()), session, current_user)
    assert caught.value.status_code == 404


@pytest.mark.asyncio
async def test_background_job_cancel_is_idempotent_and_clears_lease():
    from api.jobs import cancel_background_job

    job = SimpleNamespace(
        id=uuid.uuid4(),
        kind="feedback_reflection",
        status="running",
        worker_id="worker",
        lease_expires_at=datetime.now(timezone.utc),
        next_attempt_at=None,
        completed_at=None,
    )
    session = MagicMock()
    session.get = AsyncMock(return_value=job)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.add = MagicMock()

    result = await cancel_background_job(str(job.id), session, None)
    assert result["status"] == "cancelled"
    assert job.worker_id is None
    assert job.lease_expires_at is None
    session.commit.assert_awaited_once()

    session.commit.reset_mock()
    result = await cancel_background_job(str(job.id), session, None)
    assert result["status"] == "cancelled"
    session.commit.assert_not_awaited()
