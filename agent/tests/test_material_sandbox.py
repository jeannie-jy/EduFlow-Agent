"""Credential-free material parser sandbox contract tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml


def _write_request(job_dir: Path, source: bytes, *, digest: str | None = None) -> None:
    source_path = job_dir / "source.md"
    source_path.write_bytes(source)
    payload = {
        "attempt_id": "attempt-1",
        "source_name": source_path.name,
        "source_sha256": digest or hashlib.sha256(source_path.read_bytes()).hexdigest(),
    }
    (job_dir / "parse-request.json").write_text(json.dumps(payload), encoding="utf-8")


def _settings(**overrides):
    values = {
        "upload_max_size_bytes": 1024,
        "material_parse_result_max_bytes": 4096,
    }
    values.update(overrides)
    return MagicMock(**values)


def test_material_sandbox_parses_signed_source_and_writes_bounded_result(tmp_path):
    from services.material_sandbox import process_one_request

    job_dir = tmp_path / "job-1"
    job_dir.mkdir()
    _write_request(job_dir, "队列先进先出".encode())
    parsed = {"topics": ["队列"], "raw_text": "队列先进先出"}

    with (
        patch("services.material_sandbox.get_settings", return_value=_settings()),
        patch("services.material_sandbox._parse_material_path", return_value=parsed),
    ):
        assert process_one_request(tmp_path) is True

    result = json.loads((job_dir / "parse-result.json").read_text(encoding="utf-8"))
    assert result["status"] == "completed"
    assert result["parsed_result"] == parsed


def test_material_sandbox_rejects_source_modified_after_download(tmp_path):
    from services.material_sandbox import process_one_request

    job_dir = tmp_path / "job-tampered"
    job_dir.mkdir()
    _write_request(job_dir, b"modified", digest=hashlib.sha256(b"approved").hexdigest())

    with (
        patch("services.material_sandbox.get_settings", return_value=_settings()),
        patch("services.material_sandbox._parse_material_path") as parser,
    ):
        assert process_one_request(tmp_path) is True

    result = json.loads((job_dir / "parse-result.json").read_text(encoding="utf-8"))
    assert result["error_code"] == "material_integrity_failed"
    assert result["retryable"] is False
    parser.assert_not_called()


def test_material_sandbox_rejects_oversized_parser_output(tmp_path):
    from services.material_sandbox import process_one_request

    job_dir = tmp_path / "job-output"
    job_dir.mkdir()
    _write_request(job_dir, b"safe")
    parsed = {"topics": [], "raw_text": "x" * 200}

    with (
        patch(
            "services.material_sandbox.get_settings",
            return_value=_settings(material_parse_result_max_bytes=100),
        ),
        patch("services.material_sandbox._parse_material_path", return_value=parsed),
    ):
        assert process_one_request(tmp_path) is True

    result = json.loads((job_dir / "parse-result.json").read_text(encoding="utf-8"))
    assert result["error_code"] == "material_integrity_failed"
    assert result["retryable"] is False


def test_compose_material_sandbox_has_no_network_credentials_or_extra_mounts():
    compose = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / "docker-compose.yml").read_text(
            encoding="utf-8"
        )
    )
    sandbox = compose["services"]["material-sandbox"]
    environment = "\n".join(sandbox.get("environment", []))
    mounts = sandbox.get("volumes", [])

    assert sandbox["network_mode"] == "none"
    assert sandbox["read_only"] is True
    assert sandbox["cap_drop"] == ["ALL"]
    assert sandbox["pids_limit"] <= 64
    assert "API_KEY" not in environment
    assert "DATABASE_URL" not in environment
    assert "REDIS_URL" not in environment
    assert mounts == ["material_parse_data:/app/data/material-sandbox"]
