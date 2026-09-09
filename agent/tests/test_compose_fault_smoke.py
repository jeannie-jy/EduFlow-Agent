"""Unit tests for the Docker Compose fault-injection runner."""

from __future__ import annotations

import io
import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from scripts.compose_fault_smoke import (
    dependency_is_unavailable,
    main,
    probe_json,
    wait_until,
)


class _Response:
    status = 200

    def __init__(self, payload: dict) -> None:
        self._body = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self) -> bytes:
        return self._body


def test_probe_json_parses_success_response() -> None:
    with patch("urllib.request.urlopen", return_value=_Response({"status": "ok"})):
        result = probe_json("http://example.test/api/health")

    assert result.status == 200
    assert result.payload == {"status": "ok"}
    assert result.error is None


def test_probe_json_preserves_http_error_payload() -> None:
    error = urllib.error.HTTPError(
        "http://example.test/api/ready",
        503,
        "unavailable",
        {},
        io.BytesIO(b'{"status":"not_ready","checks":{"redis":"unavailable"}}'),
    )
    with patch("urllib.request.urlopen", side_effect=error):
        result = probe_json("http://example.test/api/ready")

    assert result.status == 503
    assert result.payload == {
        "status": "not_ready",
        "checks": {"redis": "unavailable"},
    }


def test_dependency_failure_requires_named_check() -> None:
    matching = MagicMock(
        status=503,
        payload={"status": "not_ready", "checks": {"database": "unavailable"}},
    )
    with patch("scripts.compose_fault_smoke.probe_json", return_value=matching):
        assert dependency_is_unavailable(
            "http://example.test", "database", request_timeout=1
        )
        assert not dependency_is_unavailable(
            "http://example.test", "redis", request_timeout=1
        )


def test_wait_until_returns_after_condition_becomes_true() -> None:
    predicate = MagicMock(side_effect=[False, True])
    with patch("scripts.compose_fault_smoke.time.sleep"):
        elapsed = wait_until(
            predicate, description="condition", timeout=1, interval=0
        )

    assert elapsed >= 0
    assert predicate.call_count == 2


def test_wait_until_raises_clear_timeout() -> None:
    with (
        patch("scripts.compose_fault_smoke.time.monotonic", side_effect=[0, 0, 2]),
        pytest.raises(TimeoutError, match="condition"),
    ):
        wait_until(lambda: False, description="condition", timeout=1, interval=0)


def test_main_writes_failure_report(tmp_path) -> None:
    report_path = tmp_path / "report.json"
    with (
        patch("scripts.compose_fault_smoke.wait_until", return_value=0),
        patch(
            "scripts.compose_fault_smoke.inject_fault",
            side_effect=RuntimeError("recovery failed"),
        ),
    ):
        exit_code = main(
            [
                "--services",
                "redis",
                "--report",
                str(report_path),
            ]
        )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert report["passed"] is False
    assert report["services"][0]["service"] == "redis"
    assert report["services"][0]["error"] == "RuntimeError: recovery failed"
