"""Credential-free filesystem-queue consumer for generated Manim scripts."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import socket
from pathlib import Path

from api.export import (
    ExportWorkspaceLimitError,
    _render_manim_sync,
    _workspace_exceeds_limit,
)
from config import get_settings

logger = logging.getLogger(__name__)
SANDBOX_ID = os.getenv("EDUFLOW_SANDBOX_ID") or socket.gethostname()


class ScriptIntegrityError(RuntimeError):
    """Prepared script changed after the privileged worker approved it."""


def process_one_request(export_root: Path) -> bool:
    """Atomically claim and render one prepared job from the shared volume."""
    for request_path in export_root.glob("*/render-request.json"):
        job_dir = request_path.parent.resolve()
        if not job_dir.is_relative_to(export_root.resolve()):
            continue
        claimed = job_dir / f"render-request.claimed-{SANDBOX_ID}.json"
        try:
            request_path.replace(claimed)
        except OSError:
            continue

        attempt_id = "unknown"
        try:
            request = json.loads(claimed.read_text(encoding="utf-8"))
            attempt_id = str(request["attempt_id"])
            quality = str(request.get("quality", "h"))
            fps = int(request.get("fps", 30))
            if quality not in {"l", "m", "h", "k"} or not 1 <= fps <= 120:
                raise ValueError("Invalid render configuration")

            scripts_dir = job_dir / "scripts"
            script_path = scripts_dir / "main.py"
            if not script_path.is_file():
                raise FileNotFoundError("Prepared Manim script is missing")
            expected_sha256 = str(request.get("script_sha256", ""))
            actual_sha256 = hashlib.sha256(script_path.read_bytes()).hexdigest()
            if len(expected_sha256) != 64 or actual_sha256 != expected_sha256:
                raise ScriptIntegrityError("Prepared script integrity check failed")

            settings = get_settings()
            if _workspace_exceeds_limit(
                job_dir,
                max_bytes=settings.export_max_workspace_bytes,
                max_files=settings.export_max_workspace_files,
            ):
                raise ExportWorkspaceLimitError(
                    "Prepared render workspace exceeds quota"
                )

            quality_flags = {"l": "-ql", "m": "-qm", "h": "-qh", "k": "-qk"}
            artifact = _render_manim_sync(
                str(script_path),
                job_dir,
                scripts_dir,
                quality_flags[quality],
                fps,
                str(job_dir / "videos"),
            )
            result = {
                "attempt_id": attempt_id,
                "status": "completed" if artifact else "failed",
                "artifact": artifact,
                "error": None if artifact else "Manim produced no MP4 artifact",
                "retryable": True,
                "error_code": None if artifact else "render_failed",
            }
        except (ExportWorkspaceLimitError, ScriptIntegrityError) as exc:
            logger.warning(
                "sandbox request rejected: job=%s reason=%s",
                job_dir.name,
                type(exc).__name__,
            )
            result = {
                "attempt_id": attempt_id,
                "status": "failed",
                "artifact": None,
                "error": (
                    "Prepared script integrity check failed"
                    if isinstance(exc, ScriptIntegrityError)
                    else "Render workspace quota exceeded"
                ),
                "retryable": False,
                "error_code": (
                    "script_integrity_failed"
                    if isinstance(exc, ScriptIntegrityError)
                    else "workspace_quota_exceeded"
                ),
            }
        except Exception:
            logger.exception("sandbox render failed: job=%s", job_dir.name)
            result = {
                "attempt_id": attempt_id,
                "status": "failed",
                "artifact": None,
                "error": "Render sandbox execution failed",
                "retryable": True,
                "error_code": "sandbox_execution_failed",
            }

        result_tmp = job_dir / f".render-result-{attempt_id}.tmp"
        result_tmp.write_text(json.dumps(result), encoding="utf-8")
        result_tmp.replace(job_dir / "render-result.json")
        claimed.unlink(missing_ok=True)
        return True
    return False


async def run_sandbox() -> None:
    settings = get_settings()
    export_root = Path(settings.export_dir).resolve()
    export_root.mkdir(parents=True, exist_ok=True)
    logger.info("credential-free render sandbox started")
    while True:
        if not process_one_request(export_root):
            await asyncio.sleep(settings.export_worker_poll_seconds)


def main() -> None:
    asyncio.run(run_sandbox())


if __name__ == "__main__":
    main()
