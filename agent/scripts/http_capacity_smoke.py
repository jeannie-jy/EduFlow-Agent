"""Run a bounded, read-only HTTP capacity smoke against an EduFlow deployment."""

from __future__ import annotations

import argparse
import json
import math
import time
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_PATHS = ("/api/health", "/api/ready", "/api/metrics/prometheus")


@dataclass(frozen=True)
class RequestSample:
    path: str
    status: int | None
    latency_ms: float
    error: str | None = None


def request_once(base_url: str, path: str, *, timeout: float) -> RequestSample:
    started = time.perf_counter()
    request = urllib.request.Request(
        f"{base_url}{path}",
        headers={"Accept": "application/json,text/plain", "User-Agent": "EduFlowCapacitySmoke/1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read(4096)
            status = response.status
        error = None
    except urllib.error.HTTPError as exc:
        exc.read(4096)
        status = exc.code
        error = str(exc)
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        status = None
        error = f"{type(exc).__name__}: {exc}"
    return RequestSample(
        path=path,
        status=status,
        latency_ms=round((time.perf_counter() - started) * 1000, 3),
        error=error,
    )


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return round(ordered[index], 3)


def summarize(samples: list[RequestSample], *, duration_seconds: float) -> dict[str, Any]:
    total = len(samples)
    failures = [sample for sample in samples if sample.status != 200]
    latencies = [sample.latency_ms for sample in samples]
    by_path: dict[str, Any] = {}
    for path in sorted({sample.path for sample in samples}):
        path_samples = [sample for sample in samples if sample.path == path]
        path_latencies = [sample.latency_ms for sample in path_samples]
        statuses = Counter(
            str(sample.status) if sample.status is not None else "transport_error"
            for sample in path_samples
        )
        by_path[path] = {
            "requests": len(path_samples),
            "status_counts": dict(sorted(statuses.items())),
            "p50_ms": _percentile(path_latencies, 0.50),
            "p95_ms": _percentile(path_latencies, 0.95),
            "p99_ms": _percentile(path_latencies, 0.99),
        }
    return {
        "schema_version": 1,
        "duration_seconds": round(duration_seconds, 3),
        "requests": total,
        "requests_per_second": round(total / duration_seconds, 3) if duration_seconds else 0,
        "failures": len(failures),
        "error_rate": round(len(failures) / total, 6) if total else 1.0,
        "p50_ms": _percentile(latencies, 0.50),
        "p95_ms": _percentile(latencies, 0.95),
        "p99_ms": _percentile(latencies, 0.99),
        "paths": by_path,
        "sample_errors": [
            {"path": sample.path, "status": sample.status, "error": sample.error}
            for sample in failures[:20]
        ],
    }


def run_capacity_smoke(
    *,
    base_url: str,
    paths: Sequence[str],
    duration: float,
    concurrency: int,
    request_timeout: float,
) -> dict[str, Any]:
    started = time.monotonic()
    deadline = started + duration

    def worker(offset: int) -> list[RequestSample]:
        local: list[RequestSample] = []
        index = offset
        while time.monotonic() < deadline:
            path = paths[index % len(paths)]
            local.append(request_once(base_url, path, timeout=request_timeout))
            index += 1
        return local

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        batches = list(executor.map(worker, range(concurrency)))
    elapsed = time.monotonic() - started
    samples = [sample for batch in batches for sample in batch]
    return summarize(samples, duration_seconds=elapsed)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--paths", nargs="+", default=list(DEFAULT_PATHS))
    parser.add_argument("--duration", type=float, default=60.0)
    parser.add_argument("--concurrency", type=int, default=16)
    parser.add_argument("--request-timeout", type=float, default=5.0)
    parser.add_argument("--max-error-rate", type=float, default=0.01)
    parser.add_argument("--min-rps", type=float, default=5.0)
    parser.add_argument("--report", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not 0 < args.duration <= 900:
        raise SystemExit("duration must be in (0, 900] seconds")
    if not 0 < args.concurrency <= 256:
        raise SystemExit("concurrency must be in [1, 256]")
    if args.request_timeout <= 0:
        raise SystemExit("request-timeout must be positive")
    if not args.paths or any(not path.startswith("/api/") for path in args.paths):
        raise SystemExit("every path must be an absolute /api/ path")
    if not 0 <= args.max_error_rate <= 1 or args.min_rps < 0:
        raise SystemExit("max-error-rate must be in [0,1] and min-rps must be non-negative")

    report = run_capacity_smoke(
        base_url=args.base_url.rstrip("/"),
        paths=tuple(args.paths),
        duration=args.duration,
        concurrency=args.concurrency,
        request_timeout=args.request_timeout,
    )
    report["thresholds"] = {
        "max_error_rate": args.max_error_rate,
        "min_requests_per_second": args.min_rps,
    }
    report["passed"] = (
        report["error_rate"] <= args.max_error_rate
        and report["requests_per_second"] >= args.min_rps
    )
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
