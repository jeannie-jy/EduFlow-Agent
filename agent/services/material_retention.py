"""Retention cleanup for owned uploaded materials."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from config import get_settings

logger = logging.getLogger(__name__)


async def cleanup_expired_materials() -> int:
    from db.database import async_session_factory
    from db.models import Material

    from services.artifact_store import get_artifact_store

    settings = get_settings()
    store = get_artifact_store()
    removed = 0
    async with async_session_factory() as session:
        rows = await session.scalars(
            select(Material).where(Material.expires_at <= datetime.now(timezone.utc))
        )
        for material in rows.all():
            if material.storage_key:
                try:
                    await store.delete(material.storage_key)
                except Exception:
                    logger.exception(
                        "expired material object deletion failed: material=%s",
                        material.id,
                    )
                    continue
            else:
                # Legacy rows remain readable and cleanable during migration.
                import shutil

                root = settings.upload_dir.resolve()
                target = (root / str(material.id)).resolve()
                if target.is_relative_to(root) and target.exists():
                    await asyncio.to_thread(shutil.rmtree, target)
            await session.delete(material)
            removed += 1
        await session.commit()
    if removed:
        logger.info("expired materials removed: count=%d", removed)
    return removed


async def run_material_retention(stop: asyncio.Event) -> None:
    settings = get_settings()
    while not stop.is_set():
        try:
            await cleanup_expired_materials()
        except Exception:
            logger.exception("material retention cleanup failed")
        try:
            await asyncio.wait_for(
                stop.wait(), timeout=settings.material_cleanup_interval_seconds
            )
        except TimeoutError:
            pass
