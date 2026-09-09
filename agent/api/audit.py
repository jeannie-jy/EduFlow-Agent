"""Administrator-only, bounded audit-event query API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_readonly_session
from db.models import AuditEvent, User
from services.redaction import redact_diagnostic

from .auth import require_admin

router = APIRouter(prefix="/audit", tags=["audit"])
_SENSITIVE_KEYS = {
    "authorization",
    "api_key",
    "apikey",
    "password",
    "prompt",
    "secret",
    "token",
}


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return (
        normalized in _SENSITIVE_KEYS
        or normalized.endswith("_token")
        or normalized.endswith("_password")
        or normalized.endswith("_secret")
        or normalized.endswith("_api_key")
    )


def _safe_details(value: Any, *, depth: int = 0) -> Any:
    """Return a bounded, redacted JSON-compatible audit summary."""
    if depth >= 4:
        return "[TRUNCATED]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return redact_diagnostic(value, max_length=500)
    if isinstance(value, list):
        return [_safe_details(item, depth=depth + 1) for item in value[:50]]
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for raw_key, item in list(value.items())[:50]:
            key = str(raw_key)[:100]
            if _is_sensitive_key(key):
                result[key] = "[REDACTED]"
            else:
                result[key] = _safe_details(item, depth=depth + 1)
        return result
    return redact_diagnostic(value, max_length=500)


@router.get("/events")
async def list_audit_events(
    session: AsyncSession = Depends(get_readonly_session),
    _admin: Annotated[User, Depends(require_admin)] = None,
    actor_id: uuid.UUID | None = Query(default=None),
    action: str | None = Query(default=None, min_length=1, max_length=100),
    resource_type: str | None = Query(default=None, min_length=1, max_length=100),
    resource_id: str | None = Query(default=None, min_length=1, max_length=200),
    request_id: str | None = Query(default=None, min_length=1, max_length=100),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    before_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    """List newest-first events with cursor pagination and exact-match filters."""
    predicates = []
    if actor_id is not None:
        predicates.append(AuditEvent.actor_id == actor_id)
    if action is not None:
        predicates.append(AuditEvent.action == action)
    if resource_type is not None:
        predicates.append(AuditEvent.resource_type == resource_type)
    if resource_id is not None:
        predicates.append(AuditEvent.resource_id == resource_id)
    if request_id is not None:
        predicates.append(AuditEvent.request_id == request_id)
    if since is not None:
        predicates.append(AuditEvent.created_at >= since)
    if until is not None:
        predicates.append(AuditEvent.created_at < until)
    if before_id is not None:
        predicates.append(AuditEvent.id < before_id)

    query = select(AuditEvent)
    if predicates:
        query = query.where(*predicates)
    result = await session.execute(
        query.order_by(AuditEvent.id.desc()).limit(limit + 1)
    )
    rows = list(result.scalars().all())
    has_more = len(rows) > limit
    events = rows[:limit]

    return {
        "events": [
            {
                "id": event.id,
                "actor_id": str(event.actor_id) if event.actor_id else None,
                "action": event.action,
                "resource_type": event.resource_type,
                "resource_id": event.resource_id,
                "request_id": event.request_id,
                "details": _safe_details(event.details),
                "created_at": (
                    event.created_at.isoformat() if event.created_at else None
                ),
            }
            for event in events
        ],
        "next_before_id": events[-1].id if has_more and events else None,
    }
