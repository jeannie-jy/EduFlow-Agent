"""Database-authoritative public beta quota accounting."""

from __future__ import annotations

import hashlib
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from db.models import (
    ExportJobModel,
    Material,
    Project,
    UsageBucket,
    UsageLedger,
    UserQuotaPolicy,
    WorkflowRun,
)


@contextmanager
def user_llm_limits_scope(limits: tuple[int, float]):
    from services.telemetry import llm_budget_limits_scope
    with llm_budget_limits_scope(*limits):
        yield


async def resolve_user_llm_limits(session: AsyncSession, user_id: uuid.UUID) -> tuple[int, float]:
    policy = await session.get(UserQuotaPolicy, user_id)
    settings = get_settings()
    overrides = policy.limits if policy else {}
    monthly_cap = overrides.get("monthly_reference_cost_usd")
    max_cost = float(settings.llm_request_max_cost_usd)
    if monthly_cap is not None:
        now = datetime.now(UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        used = float(await session.scalar(select(func.coalesce(func.sum(WorkflowRun.estimated_cost_usd), 0.0)).join(
            Project, Project.id == WorkflowRun.project_id
        ).where(WorkflowRun.started_at >= month_start, Project.owner_id == str(user_id))) or 0.0)
        max_cost = min(max_cost, max(0.01, float(monthly_cap) - used))
    return (
        int(overrides.get("task_max_tokens", settings.llm_request_max_tokens)),
        max_cost,
    )


async def ensure_monthly_reference_cost_capacity(session: AsyncSession, *, user_id: uuid.UUID) -> None:
    policy = await session.get(UserQuotaPolicy, user_id)
    cap = (policy.limits or {}).get("monthly_reference_cost_usd") if policy else None
    if cap is None:
        return
    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    used = float(await session.scalar(select(func.coalesce(func.sum(WorkflowRun.estimated_cost_usd), 0.0)).join(
        Project, Project.id == WorkflowRun.project_id
    ).where(WorkflowRun.started_at >= month_start, Project.owner_id == str(user_id))) or 0.0)
    if used >= float(cap):
        raise QuotaExceededError("reference_cost_usd", "month", int(float(cap) * 100))


class QuotaExceededError(RuntimeError):
    def __init__(self, resource: str, period: str, limit: int):
        super().__init__(f"{resource} {period} quota exceeded")
        self.resource = resource
        self.period = period
        self.limit = limit


def _period_starts(now: datetime) -> dict[str, datetime]:
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return {"day": day, "month": day.replace(day=1)}


def _terminal_idempotency_key(reservation_key: str, state: str) -> str:
    """Keep terminal ledger keys within the database's 200-char bound."""
    digest = hashlib.sha256(reservation_key.encode("utf-8")).hexdigest()
    return f"quota:{state}:{digest}"


def _limits(resource: str, overrides: dict | None = None) -> dict[str, int]:
    settings = get_settings()
    if resource == "generation":
        defaults = {"day": settings.quota_generation_daily, "month": settings.quota_generation_monthly}
        prefix = "generation"
    elif resource == "video":
        defaults = {"day": settings.quota_video_daily, "month": settings.quota_video_monthly}
        prefix = "video"
    else:
        raise ValueError(f"Unsupported quota resource: {resource}")
    values = dict(overrides or {})
    return {
        period: int(values.get(f"{prefix}_{period}", default))
        for period, default in defaults.items()
    }


def _total_limit(resource: str, overrides: dict | None = None) -> int:
    settings = get_settings()
    defaults = {
        "projects": settings.quota_projects,
        "material_bytes": settings.quota_material_bytes,
        "artifact_bytes": settings.quota_artifact_bytes,
        "generation_concurrent": settings.quota_generation_concurrent,
        "video_concurrent": settings.quota_video_concurrent,
    }
    if resource not in defaults:
        raise ValueError(f"Unsupported total quota resource: {resource}")
    return int((overrides or {}).get(resource, defaults[resource]))


async def quota_limit(session: AsyncSession, *, user_id: uuid.UUID, resource: str) -> int:
    policy = await session.get(UserQuotaPolicy, user_id)
    if policy is not None and policy.is_suspended:
        raise QuotaExceededError(resource, "suspended", 0)
    return _total_limit(resource, policy.limits if policy else None)


async def _lock_scope(session: AsyncSession, user_id: uuid.UUID, resource: str) -> None:
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        digest = hashlib.sha256(f"{user_id}:{resource}".encode()).digest()[:8]
        lock_id = int.from_bytes(digest, "big", signed=True)
        await session.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})


async def acquire_quota_lock(session: AsyncSession, *, user_id: uuid.UUID, resource: str) -> None:
    """Serialize admission checks for a user/resource until the DB transaction ends.

    Callers use this immediately before checking active work and reserving a
    quota unit.  PostgreSQL's transaction-scoped advisory lock closes the
    check-then-insert race across API replicas; SQLite/dev remains a no-op.
    """
    await _lock_scope(session, user_id, resource)


async def consume_quota(
    session: AsyncSession, *, user_id: uuid.UUID, resource: str,
    idempotency_key: str, amount: int = 1, details: dict | None = None,
) -> bool:
    """Consume daily and monthly quota atomically; return False for an idempotent replay."""
    if amount < 1:
        raise ValueError("Quota amount must be positive")
    await _lock_scope(session, user_id, resource)
    policy = await session.get(UserQuotaPolicy, user_id)
    if policy is not None and policy.is_suspended:
        raise QuotaExceededError(resource, "suspended", 0)
    existing = await session.scalar(select(UsageLedger).where(
        UsageLedger.user_id == user_id,
        UsageLedger.resource == resource,
        UsageLedger.idempotency_key == idempotency_key,
    ))
    if existing is not None:
        return False

    now = datetime.now(UTC)
    starts = _period_starts(now)
    for period, limit in _limits(resource, policy.limits if policy else None).items():
        bucket = await session.scalar(
            select(UsageBucket).where(
                UsageBucket.user_id == user_id,
                UsageBucket.resource == resource,
                UsageBucket.period == period,
                UsageBucket.period_start == starts[period],
            ).with_for_update()
        )
        consumed = int(bucket.consumed if bucket else 0)
        if consumed + amount > limit:
            raise QuotaExceededError(resource, period, limit)
        if bucket is None:
            bucket = UsageBucket(
                id=uuid.uuid4(), user_id=user_id, resource=resource,
                period=period, period_start=starts[period], consumed=0,
            )
            session.add(bucket)
        bucket.consumed = consumed + amount

    session.add(UsageLedger(
        id=uuid.uuid4(), user_id=user_id, resource=resource, amount=amount,
        idempotency_key=idempotency_key, details=details,
    ))
    await session.flush()
    return True


async def reserve_quota(
    session: AsyncSession, *, user_id: uuid.UUID, resource: str,
    idempotency_key: str, amount: int = 1, details: dict | None = None,
) -> bool:
    """Reserve quota for a task until it is settled or released.

    Reservations intentionally use the existing append-only ledger.  The
    bucket counter includes a reservation immediately (so concurrent API
    replicas cannot oversell); a later release writes a compensating ledger
    entry and decrements the same historical day/month buckets.  A settlement
    writes a zero-amount terminal entry and leaves the consumed counter in
    place.  Replays are idempotent for all three transitions.
    """
    if amount < 1:
        raise ValueError("Quota amount must be positive")
    await _lock_scope(session, user_id, resource)
    policy = await session.get(UserQuotaPolicy, user_id)
    if policy is not None and policy.is_suspended:
        raise QuotaExceededError(resource, "suspended", 0)
    existing = await session.scalar(select(UsageLedger).where(
        UsageLedger.user_id == user_id,
        UsageLedger.resource == resource,
        UsageLedger.idempotency_key == idempotency_key,
    ))
    if existing is not None:
        return False

    now = datetime.now(UTC)
    starts = _period_starts(now)
    for period, limit in _limits(resource, policy.limits if policy else None).items():
        bucket = await session.scalar(
            select(UsageBucket).where(
                UsageBucket.user_id == user_id,
                UsageBucket.resource == resource,
                UsageBucket.period == period,
                UsageBucket.period_start == starts[period],
            ).with_for_update()
        )
        consumed = int(bucket.consumed if bucket else 0)
        if consumed + amount > limit:
            raise QuotaExceededError(resource, period, limit)
        if bucket is None:
            bucket = UsageBucket(
                id=uuid.uuid4(), user_id=user_id, resource=resource,
                period=period, period_start=starts[period], consumed=0,
            )
            session.add(bucket)
        bucket.consumed = consumed + amount

    reservation_details = dict(details or {})
    reservation_details.update({
        "_quota_state": "reserved",
        "_quota_amount": amount,
        "_quota_period_starts": {period: value.isoformat() for period, value in starts.items()},
    })
    session.add(UsageLedger(
        id=uuid.uuid4(), user_id=user_id, resource=resource, amount=amount,
        idempotency_key=idempotency_key, details=reservation_details,
    ))
    await session.flush()
    return True


async def _reservation_row(
    session: AsyncSession, *, user_id: uuid.UUID, resource: str, idempotency_key: str,
) -> UsageLedger | None:
    row = await session.scalar(select(UsageLedger).where(
        UsageLedger.user_id == user_id,
        UsageLedger.resource == resource,
        UsageLedger.idempotency_key == idempotency_key,
    ))
    if row is None or not isinstance(row.details, dict):
        return None
    return row if row.details.get("_quota_state") == "reserved" else None


async def _reservation_terminal_exists(
    session: AsyncSession, *, user_id: uuid.UUID, resource: str, idempotency_key: str,
) -> bool:
    rows = list((await session.scalars(select(UsageLedger).where(
        UsageLedger.user_id == user_id,
        UsageLedger.resource == resource,
    ))).all())
    return any(
        isinstance(row.details, dict)
        and row.details.get("_quota_reservation") == idempotency_key
        and row.details.get("_quota_state") in {"settled", "released"}
        for row in rows
    )


async def settle_quota(
    session: AsyncSession, *, user_id: uuid.UUID, resource: str, idempotency_key: str,
) -> bool:
    """Mark a reservation as successfully consumed without changing counters."""
    await _lock_scope(session, user_id, resource)
    reservation = await _reservation_row(
        session, user_id=user_id, resource=resource, idempotency_key=idempotency_key
    )
    if reservation is None or await _reservation_terminal_exists(
        session, user_id=user_id, resource=resource, idempotency_key=idempotency_key
    ):
        return False
    session.add(UsageLedger(
        id=uuid.uuid4(), user_id=user_id, resource=resource, amount=0,
        idempotency_key=_terminal_idempotency_key(idempotency_key, "settled"), details={
            "_quota_state": "settled", "_quota_reservation": idempotency_key,
        },
    ))
    await session.flush()
    return True


async def release_quota(
    session: AsyncSession, *, user_id: uuid.UUID, resource: str, idempotency_key: str,
) -> bool:
    """Release an unstarted reservation and append an auditable compensation."""
    await _lock_scope(session, user_id, resource)
    reservation = await _reservation_row(
        session, user_id=user_id, resource=resource, idempotency_key=idempotency_key
    )
    if reservation is None or await _reservation_terminal_exists(
        session, user_id=user_id, resource=resource, idempotency_key=idempotency_key
    ):
        return False
    details = reservation.details or {}
    amount = int(details.get("_quota_amount", reservation.amount) or 0)
    raw_starts = details.get("_quota_period_starts")
    starts = {}
    if isinstance(raw_starts, dict):
        for period, value in raw_starts.items():
            try:
                starts[str(period)] = datetime.fromisoformat(str(value))
            except (TypeError, ValueError):
                continue
    if amount > 0 and starts:
        for period in ("day", "month"):
            period_start = starts.get(period)
            if period_start is None:
                continue
            bucket = await session.scalar(select(UsageBucket).where(
                UsageBucket.user_id == user_id,
                UsageBucket.resource == resource,
                UsageBucket.period == period,
                UsageBucket.period_start == period_start,
            ).with_for_update())
            if bucket is not None:
                bucket.consumed = max(0, int(bucket.consumed) - amount)
    session.add(UsageLedger(
        id=uuid.uuid4(), user_id=user_id, resource=resource, amount=-amount,
        idempotency_key=_terminal_idempotency_key(idempotency_key, "released"), details={
            "_quota_state": "released", "_quota_reservation": idempotency_key,
            "amount": amount,
        },
    ))
    await session.flush()
    return True


async def ensure_material_capacity(
    session: AsyncSession, *, user_id: uuid.UUID, incoming_bytes: int,
) -> None:
    await _lock_scope(session, user_id, "material_bytes")
    used = int(await session.scalar(select(func.coalesce(func.sum(Material.size_bytes), 0)).where(
        Material.owner_id == user_id,
    )) or 0)
    limit = await quota_limit(session, user_id=user_id, resource="material_bytes")
    if used + incoming_bytes > limit:
        raise QuotaExceededError("material_bytes", "total", limit)


async def ensure_project_capacity(session: AsyncSession, *, user_id: uuid.UUID) -> None:
    await _lock_scope(session, user_id, "projects")
    used = int(await session.scalar(select(func.count(Project.id)).where(
        Project.owner_id == str(user_id),
    )) or 0)
    limit = await quota_limit(session, user_id=user_id, resource="projects")
    if used + 1 > limit:
        raise QuotaExceededError("projects", "total", limit)


async def ensure_artifact_capacity(
    session: AsyncSession, *, user_id: uuid.UUID, incoming_bytes: int,
) -> None:
    await _lock_scope(session, user_id, "artifact_bytes")
    rows = list((await session.scalars(
        select(ExportJobModel).join(Project, Project.id == ExportJobModel.project_id).where(
            Project.owner_id == str(user_id), ExportJobModel.status == "completed",
        )
    )).all())
    used = sum(
        int(item.get("size_bytes", 0) or 0)
        for row in rows for item in (row.artifacts or []) if isinstance(item, dict)
    )
    limit = await quota_limit(session, user_id=user_id, resource="artifact_bytes")
    if used + incoming_bytes > limit:
        raise QuotaExceededError("artifact_bytes", "total", limit)


async def usage_snapshot(session: AsyncSession, user_id: uuid.UUID) -> dict[str, object]:
    now = datetime.now(UTC)
    starts = _period_starts(now)
    rows = list((await session.scalars(select(UsageBucket).where(
        UsageBucket.user_id == user_id,
        UsageBucket.period_start.in_(starts.values()),
    ))).all())
    values = {(row.resource, row.period): int(row.consumed) for row in rows}
    policy = await session.get(UserQuotaPolicy, user_id)
    limits = {
        resource: _limits(resource, policy.limits if policy else None)
        for resource in ("generation", "video")
    }
    resources = {
        resource: {
            period: {"used": values.get((resource, period), 0), "limit": value}
            for period, value in resource_limits.items()
        }
        for resource, resource_limits in limits.items()
    }
    tokens = (await session.execute(select(
        func.coalesce(func.sum(WorkflowRun.input_tokens), 0),
        func.coalesce(func.sum(WorkflowRun.output_tokens), 0),
        func.coalesce(func.sum(WorkflowRun.estimated_cost_usd), 0.0),
    ).join(Project, Project.id == WorkflowRun.project_id).where(
        WorkflowRun.started_at >= starts["month"],
        Project.owner_id == str(user_id),
    ))).one()
    settings = get_settings()
    policy_limits = policy.limits if policy else None
    project_count = int(await session.scalar(select(func.count(Project.id)).where(
        Project.owner_id == str(user_id),
    )) or 0)
    material_bytes = int(await session.scalar(select(func.coalesce(func.sum(Material.size_bytes), 0)).where(
        Material.owner_id == user_id,
    )) or 0)
    export_rows = list((await session.scalars(
        select(ExportJobModel).join(Project, Project.id == ExportJobModel.project_id).where(
            Project.owner_id == str(user_id), ExportJobModel.status == "completed",
        )
    )).all())
    artifact_bytes = sum(
        int(item.get("size_bytes", 0) or 0)
        for row in export_rows for item in (row.artifacts or []) if isinstance(item, dict)
    )
    return {
        "resources": resources,
        "is_suspended": bool(policy.is_suspended) if policy else False,
        "llm_limits": {
            "task_max_tokens": int((policy_limits or {}).get("task_max_tokens", settings.llm_request_max_tokens)),
            "monthly_reference_cost_usd": float((policy_limits or {}).get("monthly_reference_cost_usd", settings.llm_request_max_cost_usd)),
        },
        "limits": {
            "projects": {"used": project_count, "limit": _total_limit("projects", policy_limits)},
            "material_bytes": {"used": material_bytes, "limit": _total_limit("material_bytes", policy_limits)},
            "artifact_bytes": {"used": artifact_bytes, "limit": _total_limit("artifact_bytes", policy_limits)},
        },
        "model_usage_month": {
            "input_tokens": int(tokens[0]),
            "output_tokens": int(tokens[1]),
            "estimated_cost_usd": round(float(tokens[2]), 6),
            "notice": "Provider billing is authoritative; this estimate covers EduFlow calls only.",
        },
    }
