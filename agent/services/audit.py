"""Append-only audit-event writer used inside business transactions."""

from __future__ import annotations

import uuid
from typing import Any

from db.models import AuditEvent
from services.telemetry import request_id_var


def record_audit(
    session,
    *,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    actor_id: uuid.UUID | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Append an event to the caller's transaction; never store secrets or payloads."""
    session.add(AuditEvent(
        actor_id=actor_id,
        action=action[:100],
        resource_type=resource_type[:100],
        resource_id=resource_id[:200] if resource_id else None,
        request_id=request_id_var.get()[:100],
        details=details,
    ))
