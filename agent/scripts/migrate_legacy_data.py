"""Assign legacy ownerless rows and optionally copy local materials to ArtifactStore.

The command is a dry run unless ``--apply`` is supplied. Legacy source files are
kept in place so rollback remains possible after a successful migration.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from db.database import async_session_factory, close_database
from db.models import BackgroundJob, Material, Project, User
from services.artifact_store import ArtifactStore, get_artifact_store
from services.audit import record_audit


def legacy_material_source(material: Material, upload_root: Path) -> Path:
    root = upload_root.resolve()
    source = (root / str(material.id) / material.stored_filename).resolve()
    if not source.is_relative_to(root):
        raise ValueError(f"Legacy material path escapes upload root: {material.id}")
    return source


async def migrate_legacy_data(
    session: AsyncSession,
    *,
    owner_email: str,
    apply: bool,
    migrate_material_files: bool,
    upload_root: Path,
    store: ArtifactStore | None = None,
) -> dict[str, Any]:
    owner = await session.scalar(
        select(User)
        .where(func.lower(User.email) == owner_email.strip().lower())
        .with_for_update()
    )
    if owner is None or not owner.is_active:
        raise ValueError("Migration owner must be an existing active user")

    projects = list((await session.execute(
        select(Project).where(Project.owner_id.is_(None)).with_for_update()
    )).scalars().all())
    materials = list((await session.execute(
        select(Material).where(Material.owner_id.is_(None)).with_for_update()
    )).scalars().all())
    jobs = list((await session.execute(
        select(BackgroundJob).where(BackgroundJob.owner_id.is_(None)).with_for_update()
    )).scalars().all())
    legacy_files = list((await session.execute(
        select(Material).where(Material.storage_key.is_(None)).with_for_update()
    )).scalars().all()) if migrate_material_files else []

    file_sources = [(material, legacy_material_source(material, upload_root)) for material in legacy_files]
    missing = [str(material.id) for material, source in file_sources if not source.is_file()]
    report: dict[str, Any] = {
        "apply": apply,
        "owner_id": str(owner.id),
        "owner_email": owner.email,
        "ownerless_projects": len(projects),
        "ownerless_materials": len(materials),
        "ownerless_background_jobs": len(jobs),
        "legacy_material_files": len(legacy_files),
        "missing_material_file_count": len(missing),
        "missing_material_ids": missing[:100],
        "migrated_material_files": 0,
    }
    if not apply:
        await session.rollback()
        return report
    if missing:
        raise FileNotFoundError(
            "Legacy material preflight failed; no database changes committed: "
            + ", ".join(missing[:10])
        )

    for project in projects:
        project.owner_id = str(owner.id)
    for material in materials:
        material.owner_id = owner.id
    for job in jobs:
        job.owner_id = owner.id

    if file_sources:
        artifact_store = store or get_artifact_store()
        for material, source in file_sources:
            suffix = Path(material.stored_filename).suffix.lower()
            key = f"materials/{material.id}/source{suffix}"
            stored = await artifact_store.put_file(key, source, material.media_type)
            if stored.size_bytes != material.size_bytes:
                raise ValueError(f"Material size mismatch during migration: {material.id}")
            material.storage_key = stored.key
            report["migrated_material_files"] += 1

    record_audit(
        session,
        action="admin.legacy_data.migrate",
        resource_type="user",
        resource_id=str(owner.id),
        actor_id=owner.id,
        details={key: value for key, value in report.items() if key != "missing_material_ids"},
    )
    await session.flush()
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-email", required=True, help="active user receiving legacy rows")
    parser.add_argument("--apply", action="store_true", help="commit changes; otherwise only report")
    parser.add_argument(
        "--migrate-material-files",
        action="store_true",
        help="copy storage_key=NULL files into the configured ArtifactStore",
    )
    return parser.parse_args()


async def async_main() -> int:
    try:
        args = parse_args()
        settings = get_settings()
        async with async_session_factory() as session:
            try:
                report = await migrate_legacy_data(
                    session,
                    owner_email=args.owner_email,
                    apply=args.apply,
                    migrate_material_files=args.migrate_material_files,
                    upload_root=settings.upload_dir,
                )
                if args.apply:
                    await session.commit()
            except Exception:
                await session.rollback()
                raise
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    finally:
        await close_database()


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
