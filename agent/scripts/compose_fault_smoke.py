"""Inject Docker Compose dependency failures and verify API recovery.

This script deliberately avoids generation endpoints and paid model calls. It
validates the deployment contract instead: the API stays live, readiness names
the failed dependency, and readiness recovers after the container is restarted.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPENDENCY_NAMES = {
    "redis": "redis",
    "postgres": "database",
    "minio": "artifact_store",
}


@dataclass(frozen=True)
class HttpProbe:
    status: int | None
    payload: dict[str, Any] | None
    error: str | None = None


@dataclass(frozen=True)
class FaultResult:
    service: str
    dependency: str
    detection_seconds: float
    recovery_seconds: float
    passed: bool = True
    error: str | None = None


def probe_json(url: str, *, timeout: float = 5.0) -> HttpProbe:
    """Fetch a JSON endpoint while preserving non-2xx response bodies."""
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            return HttpProbe(response.status, json.loads(body))
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read())
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = None
        return HttpProbe(exc.code, payload, str(exc))
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        return HttpProbe(None, None, str(exc))


def wait_until(
    predicate: Callable[[], bool],
    *,
    description: str,
    timeout: float,
    interval: float,
) -> float:
    """Poll a condition and return elapsed seconds, or raise on timeout."""
    started = time.monotonic()
    deadline = started + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            if predicate():
                return time.monotonic() - started
        except Exception as exc:  # pragma: no cover - retained for CLI diagnostics
            last_error = exc
        time.sleep(interval)
    suffix = f"; last error: {last_error}" if last_error else ""
    raise TimeoutError(f"Timed out waiting for {description}{suffix}")


def run_compose(arguments: Sequence[str], *, cwd: Path = REPO_ROOT) -> None:
    command = ["docker", "compose", *arguments]
    print(f"+ {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def is_live(base_url: str, *, request_timeout: float) -> bool:
    probe = probe_json(f"{base_url}/api/health", timeout=request_timeout)
    return (
        probe.status == 200
        and probe.payload is not None
        and probe.payload.get("status") == "ok"
    )


def is_ready(base_url: str, *, request_timeout: float) -> bool:
    probe = probe_json(f"{base_url}/api/ready", timeout=request_timeout)
    return (
        probe.status == 200
        and probe.payload is not None
        and probe.payload.get("status") == "ready"
    )


def dependency_is_unavailable(
    base_url: str,
    dependency: str,
    *,
    request_timeout: float,
) -> bool:
    probe = probe_json(f"{base_url}/api/ready", timeout=request_timeout)
    return (
        probe.status == 503
        and probe.payload is not None
        and probe.payload.get("status") == "not_ready"
        and probe.payload.get("checks", {}).get(dependency) == "unavailable"
    )


def inject_fault(
    service: str,
    *,
    base_url: str,
    timeout: float,
    interval: float,
    request_timeout: float,
) -> FaultResult:
    dependency = DEPENDENCY_NAMES[service]
    print(f"\nInjecting {service} outage (readiness check: {dependency})", flush=True)
    run_compose(["stop", "--timeout", "10", service])
    restarted = False
    try:
        detection_seconds = wait_until(
            lambda: dependency_is_unavailable(
                base_url, dependency, request_timeout=request_timeout
            ),
            description=f"{dependency}=unavailable",
            timeout=timeout,
            interval=interval,
        )
        if not is_live(base_url, request_timeout=request_timeout):
            raise RuntimeError("API liveness failed during dependency outage")

        run_compose(["start", service])
        restarted = True
        recovery_seconds = wait_until(
            lambda: is_ready(base_url, request_timeout=request_timeout),
            description="full API readiness recovery",
            timeout=timeout,
            interval=interval,
        )
        result = FaultResult(
            service=service,
            dependency=dependency,
            detection_seconds=round(detection_seconds, 3),
            recovery_seconds=round(recovery_seconds, 3),
        )
        print(json.dumps(asdict(result), ensure_ascii=False), flush=True)
        return result
    finally:
        if not restarted:
            # Never intentionally leave a developer's dependency stopped.
            run_compose(["start", service])
            wait_until(
                lambda: is_ready(base_url, request_timeout=request_timeout),
                description="readiness after emergency recovery",
                timeout=timeout,
                interval=interval,
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--services",
        nargs="+",
        choices=tuple(DEPENDENCY_NAMES),
        default=list(DEPENDENCY_NAMES),
    )
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--request-timeout", type=float, default=5.0)
    parser.add_argument("--report", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    base_url = args.base_url.rstrip("/")
    wait_until(
        lambda: is_ready(base_url, request_timeout=args.request_timeout),
        description="initial API readiness",
        timeout=args.timeout,
        interval=args.interval,
    )

    results: list[FaultResult] = []
    for service in args.services:
        try:
            results.append(
                inject_fault(
                    service,
                    base_url=base_url,
                    timeout=args.timeout,
                    interval=args.interval,
                    request_timeout=args.request_timeout,
                )
            )
        except Exception as exc:
            failed = FaultResult(
                service=service,
                dependency=DEPENDENCY_NAMES[service],
                detection_seconds=0,
                recovery_seconds=0,
                passed=False,
                error=f"{type(exc).__name__}: {exc}",
            )
            results.append(failed)
            print(json.dumps(asdict(failed), ensure_ascii=False), flush=True)
    report = {
        "schema_version": 1,
        "base_url": base_url,
        "services": [asdict(result) for result in results],
        "passed": all(result.passed for result in results),
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    if report["passed"]:
        print(f"\nFault smoke passed for {len(results)} services.", flush=True)
        return 0
    print("\nFault smoke failed; inspect the JSON report and Compose logs.", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
