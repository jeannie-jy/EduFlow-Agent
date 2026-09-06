"""Tests for bounded, administrator-only audit inspection."""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException


def _user(role: str):
    return SimpleNamespace(id=uuid.uuid4(), role=role)


@pytest.mark.asyncio
async def test_require_admin_is_strict_in_optional_auth_mode():
    from api.auth import require_admin

    with pytest.raises(HTTPException) as anonymous:
        await require_admin(None)
    assert anonymous.value.status_code == 401

    with pytest.raises(HTTPException) as teacher:
        await require_admin(_user("teacher"))
    assert teacher.value.status_code == 403

    admin = _user("admin")
    assert await require_admin(admin) is admin


def test_audit_details_are_bounded_and_redacted():
    from api.audit import _safe_details

    result = _safe_details(
        {
            "token": "must-not-leak",
            "access_token": "also-must-not-leak",
            "diagnostic": "api_key=secret C:\\Users\\name\\private.txt",
            "items": list(range(60)),
            "nested": {"a": {"b": {"c": {"d": "too deep"}}}},
        }
    )

    assert result["token"] == "[REDACTED]"
    assert result["access_token"] == "[REDACTED]"
    assert "secret" not in result["diagnostic"]
    assert "private.txt" not in result["diagnostic"]
    assert len(result["items"]) == 50
    assert result["nested"]["a"]["b"]["c"] == "[TRUNCATED]"


@pytest.mark.asyncio
async def test_admin_audit_query_uses_cursor_and_returns_sanitized_page():
    from api.audit import list_audit_events

    now = datetime.now(timezone.utc)
    rows = [
        SimpleNamespace(
            id=event_id,
            actor_id=uuid.uuid4(),
            action="export.queue",
            resource_type="export_job",
            resource_id=f"job-{event_id}",
            request_id="req-1",
            details={"password": "hidden", "attempt": event_id},
            created_at=now,
        )
        for event_id in (3, 2, 1)
    ]
    result_proxy = MagicMock()
    result_proxy.scalars.return_value.all.return_value = rows
    session = MagicMock()
    session.execute = AsyncMock(return_value=result_proxy)

    response = await list_audit_events(
        session=session,
        _admin=_user("admin"),
        actor_id=None,
        action="export.queue",
        resource_type="export_job",
        resource_id=None,
        request_id="req-1",
        since=None,
        until=None,
        before_id=10,
        limit=2,
    )

    assert [event["id"] for event in response["events"]] == [3, 2]
    assert response["next_before_id"] == 2
    assert response["events"][0]["details"]["password"] == "[REDACTED]"
    statement = str(session.execute.await_args.args[0])
    assert "audit_events.action" in statement
    assert "audit_events.request_id" in statement
    assert "audit_events.id <" in statement
