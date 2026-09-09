"""Audit ProjectVersion, active snapshot, and Frames projection consistency.

Read-only by default. ``--repair-references`` only normalizes duplicated or
stale ``module_outputs.frames`` references; content drift is reported and must
be resolved deliberately.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from typing import Any

from sqlalchemy import select

from api.deps import parse_project_id
from db.database import async_session_factory, close_database
from db.models import Frame, Project, ProjectVersion
from services.artifact_consistency import (
    inspect_project_artifacts,
    repair_snapshot_reference,
)
from services.project_persistence import frame_row_to_dsl


async def audit(
    *, project_id: str | None = None, repair_references: bool = False
) -> dict[str, Any]:
    async with async_session_factory() as session:
        statement = select(Project).order_by(Project.id)
        if project_id:
            statement = statement.where(Project.id == parse_project_id(project_id))
        projects = list((await session.execute(statement)).scalars().all())
        reports: list[dict[str, Any]] = []
        repaired = 0

        for project in projects:
            current_version = None
            if project.current_version_id is not None:
                current_version = await session.get(
                    ProjectVersion, project.current_version_id
                )
            frame_rows = list(
                (
                    await session.execute(
                        select(Frame)
                        .where(Frame.project_id == project.id, Frame.version == 1)
                        .order_by(Frame.order_index)
                    )
                )
                .scalars()
                .all()
            )
            versions = list(
                (
                    await session.execute(
                        select(ProjectVersion).where(
                            ProjectVersion.project_id == project.id
                        )
                    )
                )
                .scalars()
                .all()
            )
            if repair_references:
                for version in versions:
                    normalized = repair_snapshot_reference(
                        version.dsl_snapshot, version.id
                    )
                    if normalized != version.dsl_snapshot:
                        version.dsl_snapshot = normalized
                        repaired += 1
                if project.current_version_id is not None and project.dsl_snapshot:
                    normalized = repair_snapshot_reference(
                        project.dsl_snapshot, project.current_version_id
                    )
                    if normalized != project.dsl_snapshot:
                        project.dsl_snapshot = normalized
                        repaired += 1

            issues = inspect_project_artifacts(
                project_snapshot=project.dsl_snapshot,
                current_version_id=project.current_version_id,
                current_version_snapshot=(
                    current_version.dsl_snapshot if current_version else None
                ),
                frame_projection=[frame_row_to_dsl(row) for row in frame_rows],
            )

            reports.append(
                {
                    "project_id": str(project.id),
                    "current_version_id": (
                        str(project.current_version_id)
                        if project.current_version_id
                        else None
                    ),
                    "version_count": len(versions),
                    "issues": issues,
                }
            )

        if repair_references:
            await session.commit()
        else:
            await session.rollback()
        return {
            "project_count": len(projects),
            "inconsistent_project_count": sum(bool(r["issues"]) for r in reports),
            "repaired_reference_count": repaired,
            "projects": reports,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", help="audit one project UUID")
    parser.add_argument(
        "--repair-references",
        action="store_true",
        help="normalize only Frames artifact references and commit them",
    )
    return parser.parse_args()


async def async_main() -> int:
    try:
        args = parse_args()
        if args.project_id:
            uuid.UUID(args.project_id)
        report = await audit(
            project_id=args.project_id,
            repair_references=args.repair_references,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1 if report["inconsistent_project_count"] else 0
    finally:
        await close_database()


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
