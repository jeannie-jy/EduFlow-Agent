"""Tests for the read-only HTTP capacity smoke reporter."""

from __future__ import annotations

import json
from unittest.mock import patch

from scripts.http_capacity_smoke import RequestSample, main, summarize


def test_summary_reports_percentiles_statuses_and_errors() -> None:
    report = summarize(
        [
            RequestSample("/api/health", 200, 10),
            RequestSample("/api/health", 200, 20),
            RequestSample("/api/ready", 503, 30, "not ready"),
            RequestSample("/api/ready", None, 40, "timeout"),
        ],
        duration_seconds=2,
    )

    assert report["requests_per_second"] == 2
    assert report["error_rate"] == 0.5
    assert report["p50_ms"] == 20
    assert report["p95_ms"] == 40
    assert report["paths"]["/api/ready"]["status_counts"] == {
        "503": 1,
        "transport_error": 1,
    }


def test_main_writes_report_and_enforces_thresholds(tmp_path) -> None:
    output = tmp_path / "capacity.json"
    measured = {
        "error_rate": 0.02,
        "requests_per_second": 50,
        "requests": 100,
    }
    with patch("scripts.http_capacity_smoke.run_capacity_smoke", return_value=measured):
        exit_code = main(
            [
                "--duration",
                "1",
                "--concurrency",
                "1",
                "--max-error-rate",
                "0.01",
                "--report",
                str(output),
            ]
        )

    report = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert report["passed"] is False
    assert report["thresholds"]["max_error_rate"] == 0.01


def test_main_rejects_non_api_paths() -> None:
    with patch("scripts.http_capacity_smoke.run_capacity_smoke") as runner:
        try:
            main(["--paths", "https://example.test/"])
        except SystemExit as exc:
            assert str(exc) == "every path must be an absolute /api/ path"
        else:  # pragma: no cover
            raise AssertionError("invalid path was accepted")
    runner.assert_not_called()


def test_main_rejects_unbounded_concurrency() -> None:
    try:
        main(["--concurrency", "257"])
    except SystemExit as exc:
        assert str(exc) == "concurrency must be in [1, 256]"
    else:  # pragma: no cover
        raise AssertionError("unbounded concurrency was accepted")
