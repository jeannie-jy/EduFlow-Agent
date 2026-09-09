"""PostgreSQL-backed SSE replay ledger with renewable producer leases."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterable
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

from sqlalchemy import delete, or_, select, update
from sqlalchemy.exc import IntegrityError

from config import get_settings

logger = logging.getLogger(__name__)
STREAM_END_EVENTS = {"done", "error", "waiting_approval"}


def new_stream_id() -> str:
    return str(uuid.uuid4())


def _wire_event(event_id: int, event_name: str, payload: dict) -> dict[str, str]:
    enriched = {**payload, "schema_version": "1.0", "event_id": event_id}
    return {
        "id": str(event_id),
        "event": event_name,
        "data": json.dumps(enriched, ensure_ascii=False),
    }


async def _ensure_stream(stream_id: uuid.UUID, project_id: uuid.UUID, kind: str) -> None:
    from db.database import async_session_factory
    from db.models import SSEStream

    async with async_session_factory() as session:
        retention_cutoff = datetime.now(timezone.utc) - timedelta(
            hours=get_settings().sse_event_retention_hours
        )
        await session.execute(
            delete(SSEStream).where(
                SSEStream.status == "completed",
                SSEStream.completed_at < retention_cutoff,
            )
        )
        existing = await session.get(SSEStream, stream_id)
        if existing is not None:
            if existing.project_id != project_id:
                raise PermissionError("SSE stream belongs to another project")
            return
        session.add(SSEStream(
            id=stream_id, project_id=project_id, kind=kind[:50], status="active"
        ))
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()


async def _read_events(stream_id: uuid.UUID, after: int) -> tuple[list[dict[str, str]], bool]:
    from db.database import async_session_factory
    from db.models import SSEEvent, SSEStream

    async with async_session_factory() as session:
        stream = await session.get(SSEStream, stream_id)
        if stream is None:
            return [], False
        rows = (await session.scalars(
            select(SSEEvent)
            .where(SSEEvent.stream_id == stream_id, SSEEvent.event_id > after)
            .order_by(SSEEvent.event_id)
        )).all()
        return [
            _wire_event(row.event_id, row.event_name, dict(row.payload or {}))
            for row in rows
        ], stream.status == "completed"


async def _claim(stream_id: uuid.UUID, producer_id: str) -> bool:
    from db.database import async_session_factory
    from db.models import SSEStream

    settings = get_settings()
    now = datetime.now(timezone.utc)
    async with async_session_factory() as session:
        result = await session.execute(
            update(SSEStream)
            .where(
                SSEStream.id == stream_id,
                SSEStream.status == "active",
                or_(
                    SSEStream.producer_id.is_(None),
                    SSEStream.lease_expires_at < now,
                    SSEStream.producer_id == producer_id,
                ),
            )
            .values(
                producer_id=producer_id,
                lease_expires_at=now + timedelta(seconds=settings.sse_stream_lease_seconds),
            )
        )
        await session.commit()
        return bool(result.rowcount)


async def _renew(stream_id: uuid.UUID, producer_id: str) -> bool:
    from db.database import async_session_factory
    from db.models import SSEStream

    settings = get_settings()
    async with async_session_factory() as session:
        result = await session.execute(
            update(SSEStream)
            .where(
                SSEStream.id == stream_id,
                SSEStream.status == "active",
                SSEStream.producer_id == producer_id,
            )
            .values(lease_expires_at=datetime.now(timezone.utc) + timedelta(
                seconds=settings.sse_stream_lease_seconds
            ))
        )
        await session.commit()
        return bool(result.rowcount)


async def _heartbeat(stream_id: uuid.UUID, producer_id: str, stop: asyncio.Event) -> None:
    interval = max(get_settings().sse_stream_lease_seconds / 3, 1)
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except TimeoutError:
            if not await _renew(stream_id, producer_id):
                return


async def _release(stream_id: uuid.UUID, producer_id: str) -> None:
    from db.database import async_session_factory
    from db.models import SSEStream

    async with async_session_factory() as session:
        await session.execute(
            update(SSEStream)
            .where(
                SSEStream.id == stream_id,
                SSEStream.status == "active",
                SSEStream.producer_id == producer_id,
            )
            .values(producer_id=None, lease_expires_at=None)
        )
        await session.commit()


async def _append(
    stream_id: uuid.UUID, producer_id: str, event: dict[str, str]
) -> dict[str, str]:
    from db.database import async_session_factory
    from db.models import SSEEvent, SSEStream

    async with async_session_factory() as session:
        stream = await session.scalar(
            select(SSEStream).where(SSEStream.id == stream_id).with_for_update()
        )
        if stream is None or stream.producer_id != producer_id or stream.status != "active":
            raise RuntimeError("SSE producer lease lost")
        event_id = stream.last_event_id + 1
        try:
            payload = json.loads(event.get("data", "{}"))
        except (TypeError, json.JSONDecodeError):
            payload = {"message": "Malformed server event"}
        if not isinstance(payload, dict):
            payload = {"value": payload}
        event_name = str(event.get("event") or "progress")[:50]
        session.add(SSEEvent(
            id=uuid.uuid4(), stream_id=stream_id, event_id=event_id,
            event_name=event_name, payload=payload,
        ))
        stream.last_event_id = event_id
        if event_name in STREAM_END_EVENTS:
            stream.status = "completed"
            stream.completed_at = datetime.now(timezone.utc)
            stream.producer_id = None
            stream.lease_expires_at = None
        await session.commit()
        return _wire_event(event_id, event_name, payload)


async def durable_sse_stream(
    source: AsyncIterable[dict[str, str]], *, stream_id: str, project_id: str,
    kind: str, last_event_id: int = 0,
) -> AsyncGenerator[dict[str, str], None]:
    """Replay committed events, then exclusively produce and persist new ones."""
    parsed_stream = uuid.UUID(stream_id)
    parsed_project = uuid.UUID(project_id)
    await _ensure_stream(parsed_stream, parsed_project, kind)
    cursor = max(last_event_id, 0)
    producer_id = uuid.uuid4().hex

    while True:
        replay, completed = await _read_events(parsed_stream, cursor)
        for event in replay:
            cursor = int(event["id"])
            yield event
        if completed:
            return
        if await _claim(parsed_stream, producer_id):
            break
        await asyncio.sleep(get_settings().sse_stream_poll_seconds)

    stop = asyncio.Event()
    heartbeat = asyncio.create_task(_heartbeat(parsed_stream, producer_id, stop))
    try:
        async for event in source:
            committed = await _append(parsed_stream, producer_id, event)
            cursor = int(committed["id"])
            yield committed
            if committed["event"] in STREAM_END_EVENTS:
                return
    finally:
        stop.set()
        await asyncio.gather(heartbeat, return_exceptions=True)
        await _release(parsed_stream, producer_id)
