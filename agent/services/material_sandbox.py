"""Credential-free filesystem consumer for untrusted material parsing."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import socket
from pathlib import Path

from api.materials import (
    ALLOWED_EXTENSIONS,
    _parse_material_path,
    _validate_parsed_result,
)
from config import get_settings

logger = logging.getLogger(__name__)
SANDBOX_ID = os.getenv("EDUFLOW_MATERIAL_SANDBOX_ID") or socket.gethostname()


class MaterialIntegrityError(RuntimeError):
    """The downloaded source changed after the privileged worker approved it."""


def process_one_request(root: Path) -> bool:
    """Claim, validate and parse one request without external service access."""
    resolved_root = root.resolve()
    for request_path in root.glob("*/parse-request.json"):
        job_dir = request_path.parent.resolve()
        if not job_dir.is_relative_to(resolved_root):
            continue
        claimed = job_dir / f"parse-request.claimed-{SANDBOX_ID}.json"
        try:
            request_path.replace(claimed)
        except OSError:
            continue

        attempt_id = "unknown"
        try:
            request = json.loads(claimed.read_text(encoding="utf-8"))
            attempt_id = str(request["attempt_id"])
            source_name = str(request["source_name"])
            if Path(source_name).name != source_name:
                raise MaterialIntegrityError("Unsafe material source path")
            source_path = (job_dir / source_name).resolve()
            if (
                not source_path.is_relative_to(job_dir)
                or source_path.suffix.lower() not in ALLOWED_EXTENSIONS
                or not source_path.is_file()
            ):
                raise MaterialIntegrityError(
                    "Material source is missing or unsupported"
                )
            settings = get_settings()
            if source_path.stat().st_size > settings.upload_max_size_bytes:
                raise MaterialIntegrityError("Material source exceeds the upload limit")
            expected_sha256 = str(request.get("source_sha256", ""))
            actual_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()
            if len(expected_sha256) != 64 or expected_sha256 != actual_sha256:
                raise MaterialIntegrityError("Material source integrity check failed")

            parsed = _validate_parsed_result(_parse_material_path(source_path))
            encoded = json.dumps(parsed, ensure_ascii=False).encode("utf-8")
            if len(encoded) > settings.material_parse_result_max_bytes:
                raise MaterialIntegrityError("Material parse result exceeds its limit")
            result = {
                "attempt_id": attempt_id,
                "status": "completed",
                "parsed_result": parsed,
                "error": None,
                "retryable": False,
            }
        except MaterialIntegrityError as exc:
            logger.warning(
                "material sandbox request rejected: job=%s reason=%s",
                job_dir.name,
                type(exc).__name__,
            )
            result = {
                "attempt_id": attempt_id,
                "status": "failed",
                "parsed_result": None,
                "error": "Material sandbox input failed integrity checks",
                "error_code": "material_integrity_failed",
                "retryable": False,
            }
        except Exception:
            logger.exception("material sandbox parse failed: job=%s", job_dir.name)
            result = {
                "attempt_id": attempt_id,
                "status": "failed",
                "parsed_result": None,
                "error": "Material sandbox parsing failed",
                "error_code": "material_parse_failed",
                "retryable": True,
            }

        result_tmp = job_dir / f".parse-result-{attempt_id}.tmp"
        result_tmp.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        result_tmp.replace(job_dir / "parse-result.json")
        claimed.unlink(missing_ok=True)
        return True
    return False


async def run_sandbox() -> None:
    settings = get_settings()
    root = settings.material_sandbox_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    logger.info("credential-free material parser sandbox started")
    while True:
        if not process_one_request(root):
            await asyncio.sleep(settings.task_worker_poll_seconds)


def main() -> None:
    asyncio.run(run_sandbox())


if __name__ == "__main__":
    main()
