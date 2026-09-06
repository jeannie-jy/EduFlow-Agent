"""Durable export-worker lease and role tests."""

import asyncio
import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml


def _sandbox_request(script: str, attempt_id: str) -> str:
    return json.dumps(
        {
            "attempt_id": attempt_id,
            "quality": "l",
            "fps": 24,
            "script_sha256": hashlib.sha256(script.encode("utf-8")).hexdigest(),
        }
    )


@pytest.mark.asyncio
async def test_preparer_signs_script_before_sandbox_dispatch(tmp_path):
    from api.export import _submit_and_wait_for_sandbox

    script = "from manim import *\nclass Lesson(Scene): pass"
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "main.py").write_text(script, encoding="utf-8")
    settings = MagicMock(manim_timeout_seconds=1, export_worker_poll_seconds=0.001)

    with patch("api.export.get_settings", return_value=settings):
        pending = asyncio.create_task(
            _submit_and_wait_for_sandbox(tmp_path, quality="l", fps=24)
        )
        request_path = tmp_path / "render-request.json"
        for _ in range(100):
            if request_path.exists():
                break
            await asyncio.sleep(0.001)
        request = json.loads(request_path.read_text(encoding="utf-8"))
        assert (
            request["script_sha256"]
            == hashlib.sha256((scripts_dir / "main.py").read_bytes()).hexdigest()
        )
        (tmp_path / "render-result.json").write_text(
            json.dumps({"attempt_id": request["attempt_id"], "status": "completed"}),
            encoding="utf-8",
        )
        result = await pending

    assert result["status"] == "completed"


@pytest.mark.asyncio
async def test_worker_refuses_to_run_in_api_queue_mode():
    from services.export_worker import run_worker

    with patch(
        "services.export_worker.get_settings",
        return_value=MagicMock(manim_execution_mode="queue"),
    ):
        with pytest.raises(RuntimeError, match="requires MANIM_EXECUTION_MODE=worker"):
            await run_worker()


@pytest.mark.asyncio
async def test_claim_marks_job_rendering_and_assigns_lease():
    from services.export_worker import WORKER_ID, claim_export_job

    job = MagicMock()
    job.id = "00000000-0000-0000-0000-000000000123"
    job.project_id = "00000000-0000-0000-0000-000000000001"
    job.source_version_id = uuid.uuid4()
    job.config = {"quality": "l"}
    job.attempt_count = 1
    frozen_dsl = {"frames": [{"frame_id": "frozen"}]}
    source_version = MagicMock(
        project_id=job.project_id,
        dsl_snapshot=frozen_dsl,
    )

    result_proxy = MagicMock()
    result_proxy.scalar_one_or_none.return_value = job
    session = MagicMock()
    session.execute = AsyncMock(return_value=result_proxy)
    session.get = AsyncMock(return_value=source_version)
    session.commit = AsyncMock()
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=session)
    context.__aexit__ = AsyncMock(return_value=None)

    settings = MagicMock(
        export_worker_max_attempts=3,
        manim_timeout_seconds=600,
    )
    before = datetime.now(timezone.utc)
    with (
        patch("services.export_worker.get_settings", return_value=settings),
        patch("db.database.async_session_factory", return_value=context),
    ):
        claimed = await claim_export_job()

    assert claimed["job_id"] == str(job.id)
    assert uuid.UUID(claimed["attempt_id"])
    assert claimed["attempt_no"] == 2
    assert claimed["dsl"] == frozen_dsl
    assert claimed["source_version_id"] == str(job.source_version_id)
    assert claimed["config"] == {"quality": "l"}
    assert job.status == "rendering"
    assert job.attempt_count == 2
    assert job.worker_id == WORKER_ID
    assert job.lease_expires_at > before
    session.add.assert_called_once()
    session.commit.assert_awaited_once()


def _export_dsl() -> dict:
    return {
        "project_id": "p1",
        "topic": "formula",
        "frames": [
            {
                "frame_id": "f_001",
                "title": "Formula",
                "narration": "Explain the formula",
                "visual_objects": [
                    {"id": "formula-1", "type": "formula", "latex": r"E=mc^2"}
                ],
                "animations": [{"type": "appear", "target": "formula-1"}],
            }
        ],
    }


@pytest.mark.asyncio
async def test_llm_static_validation_failure_falls_back_without_job_retry(tmp_path):
    from api.export import _do_export_async

    invalid_llm_files = {
        "main.py": (
            "from manim import *\n"
            "class Lesson(Scene):\n"
            "    def construct(self):\n"
            "        self.add(MathTex(r'E=mc^2'))\n"
        ),
        "render_config.json": "{}",
        "subtitles.srt": "",
    }
    llm_convert = AsyncMock(return_value=invalid_llm_files)

    async def successful_sandbox(export_dir, *, quality, fps):
        script = (export_dir / "scripts" / "main.py").read_text(encoding="utf-8")
        assert "MathTex(" not in script
        (export_dir / "lesson.mp4").write_bytes(b"video")
        return {
            "status": "completed",
            "artifact": {"type": "mp4", "filename": "lesson.mp4"},
        }

    settings = MagicMock(
        export_dir=str(tmp_path),
        manim_script_mode="llm",
        export_max_artifact_bytes=1024,
    )
    redis_client = MagicMock()
    publish = AsyncMock(
        side_effect=lambda _dir, _job, artifacts, **_: (True, artifacts)
    )
    with (
        patch("api.export.get_settings", return_value=settings),
        patch("redis.from_url", return_value=redis_client),
        patch(
            "adapters.manim_llm_adapter.convert_dsl_to_manim_llm", llm_convert
        ),
        patch(
            "api.export._submit_and_wait_for_sandbox",
            side_effect=successful_sandbox,
        ) as sandbox,
        patch("api.export._publish_and_persist_export_artifacts", new=publish),
    ):
        await _do_export_async(
            "00000000-0000-0000-0000-000000000999",
            _export_dsl(),
            {"quality": "l", "fps": 24},
            "redis://unused",
            MagicMock(),
        )

    assert llm_convert.await_count == 1
    assert sandbox.call_count == 1
    debug_dir = tmp_path / "00000000-0000-0000-0000-000000000999" / "debug"
    assert (debug_dir / "llm-main.py").is_file()
    assert (debug_dir / "llm-validation-errors.json").is_file()


def test_export_retry_delay_is_exponential_and_capped():
    from services.export_worker import export_retry_delay_seconds

    settings = MagicMock(
        export_retry_base_seconds=5,
        export_retry_max_seconds=12,
    )
    with (
        patch("services.export_worker.get_settings", return_value=settings),
        patch(
            "services.export_worker.random.uniform", side_effect=lambda low, high: high
        ),
    ):
        assert export_retry_delay_seconds(1) == 6
        assert export_retry_delay_seconds(2) == 12
        assert export_retry_delay_seconds(3) == 12


@pytest.mark.asyncio
async def test_failed_export_is_requeued_with_backoff_before_max_attempts():
    from services.export_worker import schedule_export_retry

    job_id = uuid.uuid4()
    job = MagicMock(
        id=job_id,
        status="failed",
        attempt_count=1,
        completed_at=datetime.now(timezone.utc),
    )
    session = MagicMock()
    session.get = AsyncMock(return_value=job)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=session)
    context.__aexit__ = AsyncMock(return_value=None)
    settings = MagicMock(
        export_worker_max_attempts=3,
        export_retry_base_seconds=5,
        export_retry_max_seconds=300,
        redis_url="redis://unneeded",
    )

    with (
        patch("services.export_worker.get_settings", return_value=settings),
        patch("services.export_worker.export_retry_delay_seconds", return_value=7),
        patch("db.database.async_session_factory", return_value=context),
        patch("redis.from_url", return_value=MagicMock()),
        patch("api.export._try_update_redis_status") as redis_update,
    ):
        scheduled = await schedule_export_retry(str(job_id), 1)

    assert scheduled is True
    assert job.status == "queued"
    assert job.error_log is None
    assert job.completed_at is None
    assert 6 <= (job.next_attempt_at - datetime.now(timezone.utc)).total_seconds() <= 7
    session.commit.assert_awaited_once()
    redis_update.assert_called_once()


@pytest.mark.asyncio
async def test_failed_export_stays_terminal_at_max_attempts():
    from services.export_worker import schedule_export_retry

    with patch(
        "services.export_worker.get_settings",
        return_value=MagicMock(export_worker_max_attempts=3),
    ):
        assert await schedule_export_retry(str(uuid.uuid4()), 3) is False


@pytest.mark.asyncio
async def test_missing_project_marks_claimed_job_failed():
    from services.export_worker import claim_export_job

    job = MagicMock(project_id="missing", attempt_count=0)
    result_proxy = MagicMock()
    result_proxy.scalar_one_or_none.return_value = job
    session = MagicMock()
    session.execute = AsyncMock(return_value=result_proxy)
    session.get = AsyncMock(return_value=None)
    session.commit = AsyncMock()
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=session)
    context.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "services.export_worker.get_settings",
            return_value=MagicMock(export_worker_max_attempts=3),
        ),
        patch("db.database.async_session_factory", return_value=context),
    ):
        claimed = await claim_export_job()

    assert claimed is None
    assert job.status == "failed"
    assert "no longer exist" in job.error_log
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_lease_heartbeat_detects_cancelled_or_reassigned_job():
    from services.export_worker import _maintain_export_lease

    async def immediate_timeout(awaitable, *, timeout):
        del timeout
        awaitable.close()
        raise TimeoutError

    with (
        patch(
            "services.export_worker.get_settings",
            return_value=MagicMock(export_worker_heartbeat_seconds=1),
        ),
        patch(
            "services.export_worker.asyncio.wait_for",
            new=immediate_timeout,
        ),
        patch(
            "services.export_worker.renew_export_lease",
            new=AsyncMock(return_value=False),
        ) as renew,
    ):
        lost = await _maintain_export_lease("job-1", asyncio.Event())

    assert lost is True
    renew.assert_awaited_once_with("job-1")


@pytest.mark.asyncio
async def test_claimed_export_stops_when_lease_is_lost():
    from services.export_worker import run_claimed_export

    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def wait_forever(*_args):
        started.set()
        try:
            await asyncio.Future()
        finally:
            cancelled.set()

    async def lose_lease(*_args):
        await started.wait()
        return True

    with (
        patch("api.export._fallback_export", new=wait_forever),
        patch(
            "services.export_worker._maintain_export_lease",
            new=lose_lease,
        ),
    ):
        await run_claimed_export({"job_id": "job-1", "dsl": {}, "config": {}})

    assert cancelled.is_set()


def test_sandbox_claims_filesystem_request_and_writes_result(tmp_path):
    from services.export_sandbox import process_one_request

    job_dir = tmp_path / "job-1"
    scripts_dir = job_dir / "scripts"
    scripts_dir.mkdir(parents=True)
    script = "from manim import *"
    (scripts_dir / "main.py").write_text(script, encoding="utf-8")
    (job_dir / "render-request.json").write_text(
        _sandbox_request(script, "attempt-1"),
        encoding="utf-8",
    )

    artifact = {"type": "mp4", "filename": "lesson.mp4", "size_bytes": 12}
    with patch(
        "services.export_sandbox._render_manim_sync", return_value=artifact
    ) as render:
        assert process_one_request(tmp_path) is True

    result = json.loads((job_dir / "render-result.json").read_text(encoding="utf-8"))
    assert result == {
        "attempt_id": "attempt-1",
        "status": "completed",
        "artifact": artifact,
        "error": None,
        "retryable": True,
        "error_code": None,
    }
    assert not (job_dir / "render-request.json").exists()
    render.assert_called_once()


def test_workspace_quota_counts_bytes_and_files_without_following_symlinks(tmp_path):
    from api.export import _workspace_exceeds_limit

    (tmp_path / "one.bin").write_bytes(b"1234")
    (tmp_path / "two.bin").write_bytes(b"5678")

    assert _workspace_exceeds_limit(tmp_path, max_bytes=7, max_files=10) is True
    assert _workspace_exceeds_limit(tmp_path, max_bytes=100, max_files=1) is True
    assert _workspace_exceeds_limit(tmp_path, max_bytes=100, max_files=10) is False


def test_sandbox_rejects_oversized_workspace_without_rendering(tmp_path):
    from services.export_sandbox import process_one_request

    job_dir = tmp_path / "job-quota"
    scripts_dir = job_dir / "scripts"
    scripts_dir.mkdir(parents=True)
    script = "from manim import *"
    (scripts_dir / "main.py").write_text(script, encoding="utf-8")
    (job_dir / "large.bin").write_bytes(b"x" * 20)
    (job_dir / "render-request.json").write_text(
        _sandbox_request(script, "attempt-quota"),
        encoding="utf-8",
    )
    settings = MagicMock(export_max_workspace_bytes=10, export_max_workspace_files=100)

    with (
        patch("services.export_sandbox.get_settings", return_value=settings),
        patch("services.export_sandbox._render_manim_sync") as render,
    ):
        assert process_one_request(tmp_path) is True

    result = json.loads((job_dir / "render-result.json").read_text(encoding="utf-8"))
    assert result["status"] == "failed"
    assert result["retryable"] is False
    assert result["error_code"] == "workspace_quota_exceeded"
    render.assert_not_called()


def test_sandbox_rejects_script_modified_after_worker_approval(tmp_path):
    from services.export_sandbox import process_one_request

    job_dir = tmp_path / "job-tampered"
    scripts_dir = job_dir / "scripts"
    scripts_dir.mkdir(parents=True)
    approved = "from manim import *\nclass Lesson(Scene): pass"
    (scripts_dir / "main.py").write_text(
        "import os\nos.system('malicious-command')", encoding="utf-8"
    )
    (job_dir / "render-request.json").write_text(
        _sandbox_request(approved, "attempt-tampered"), encoding="utf-8"
    )
    settings = MagicMock(
        export_max_workspace_bytes=1024,
        export_max_workspace_files=100,
    )

    with (
        patch("services.export_sandbox.get_settings", return_value=settings),
        patch("services.export_sandbox._render_manim_sync") as render,
    ):
        assert process_one_request(tmp_path) is True

    result = json.loads((job_dir / "render-result.json").read_text(encoding="utf-8"))
    assert result["status"] == "failed"
    assert result["retryable"] is False
    assert result["error_code"] == "script_integrity_failed"
    render.assert_not_called()


def test_compose_sandbox_has_no_network_or_service_credentials():
    compose = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / "docker-compose.yml").read_text(
            encoding="utf-8"
        )
    )
    sandbox = compose["services"]["render-sandbox"]
    environment = "\n".join(sandbox.get("environment", []))

    assert sandbox["network_mode"] == "none"
    assert sandbox["read_only"] is True
    assert sandbox["cap_drop"] == ["ALL"]
    assert "API_KEY" not in environment
    assert "DATABASE_URL" not in environment
    assert "REDIS_URL" not in environment


def test_compose_sandbox_enforces_resource_and_mount_boundaries():
    compose = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / "docker-compose.yml").read_text(
            encoding="utf-8"
        )
    )
    sandbox = compose["services"]["render-sandbox"]
    mounts = "\n".join(sandbox.get("volumes", []))

    assert sandbox["pids_limit"] <= 256
    assert sandbox["mem_limit"] == "2g"
    assert float(sandbox["cpus"]) <= 2
    assert sandbox["security_opt"] == ["no-new-privileges:true"]
    assert sandbox["tmpfs"]
    assert mounts == "render_data:/app/data/exports"
    assert "docker.sock" not in mounts.lower()


def test_compose_has_no_implicit_data_service_secrets_or_public_data_ports():
    compose_path = Path(__file__).resolve().parents[2] / "docker-compose.yml"
    raw = compose_path.read_text(encoding="utf-8")
    compose = yaml.safe_load(raw)

    assert ":-changeme" not in raw
    assert ":-minioadmin" not in raw
    assert "${DB_PASSWORD:?" in raw
    assert "${MINIO_PASSWORD:?" in raw
    for service_name in ("agent-api", "postgres", "redis", "minio"):
        assert all(
            str(port).startswith("127.0.0.1:")
            for port in compose["services"][service_name]["ports"]
        )


def test_agent_runtime_image_excludes_build_toolchain():
    dockerfile = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text(
        encoding="utf-8"
    )
    assert "FROM python:3.12-slim AS builder" in dockerfile
    assert "FROM python:3.12-slim AS runtime" in dockerfile
    runtime = dockerfile.split("FROM python:3.12-slim AS runtime", 1)[1]
    assert "build-essential" not in runtime
    assert "USER eduflow" in runtime
