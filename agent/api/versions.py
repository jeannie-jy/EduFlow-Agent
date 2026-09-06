"""版本管理 API 路由。

POST   /api/projects/{id}/versions                    保存当前版本
GET    /api/projects/{id}/versions                     版本列表
GET    /api/projects/{id}/versions/{vid}               获取指定版本
POST   /api/projects/{id}/versions/{vid}/restore       恢复到指定版本
"""

from __future__ import annotations

import logging
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_readonly_session, get_session
from db.models import User
from schema.project import CreateVersionRequest
from services.dsl_diff import diff_dsl_versions

from .auth import require_editor
from .deps import parse_project_id, safe_project_uuid

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["versions"])


async def save_version(
    project_id: str,
    dsl: dict,
    change_summary: str = "",
    session: AsyncSession | None = None,
) -> dict:
    """保存项目当前 DSL 为新版本。供其他服务层调用。"""
    if session is None:
        return {"version": 0, "id": ""}

    from db.models import Project, ProjectVersion
    from services.project_persistence import compact_frames_artifact_reference

    project_uuid = parse_project_id(project_id)
    # Serialize version-number allocation per project. This removes the previous
    # SELECT MAX + INSERT race without taking a table-wide lock.
    project = await session.get(Project, project_uuid, with_for_update=True)
    if project is None:
        raise ValueError("Project not found while saving version")

    # Project row lock serializes MAX + INSERT for this project.
    result = await session.execute(
        select(func.max(ProjectVersion.version)).where(
            ProjectVersion.project_id == project_uuid
        )
    )
    max_ver = result.scalar() or 0

    version_id = uuid.uuid4()
    compacted_dsl = compact_frames_artifact_reference(dsl, version_id)
    version = ProjectVersion(
        id=version_id,
        project_id=project_uuid,
        version=max_ver + 1,
        dsl_snapshot=deepcopy(compacted_dsl),
        change_summary=change_summary
        or f"Auto-saved at {datetime.now(timezone.utc).isoformat()}",
    )
    session.add(version)
    await session.flush()
    project.current_version_id = version.id
    project.dsl_snapshot = deepcopy(compacted_dsl)

    logger.info("版本已保存: project=%s version=%d", project_id, version.version)
    return {"version": version.version, "id": str(version.id)}


@router.post("/{project_id}/versions", status_code=201)
async def create_version(
    project_id: str,
    body: CreateVersionRequest,
    session: AsyncSession = Depends(get_session),
    _editor: Annotated[User | None, Depends(require_editor)] = None,
) -> dict:
    """手动保存当前 DSL 为新版本。"""
    from db.models import Project as ProjectModel

    project = await session.get(ProjectModel, parse_project_id(project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.dsl_snapshot:
        raise HTTPException(status_code=400, detail="Project has no DSL to save")

    return await save_version(
        project_id,
        project.dsl_snapshot,
        body.change_summary,
        session,
    )


@router.get("/{project_id}/versions")
async def list_versions(
    project_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """获取项目的所有历史版本。"""
    from db.models import Project, ProjectVersion

    project = await session.get(Project, parse_project_id(project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    query = (
        select(ProjectVersion)
        .where(ProjectVersion.project_id == parse_project_id(project_id))
        .order_by(ProjectVersion.version.desc())
    )
    result = await session.execute(query)
    versions = result.scalars().all()

    return {
        "versions": [
            {
                "id": str(v.id),
                "version": v.version,
                "change_summary": v.change_summary,
                "created_at": v.created_at.isoformat() if v.created_at else None,
                "is_current": v.id == project.current_version_id,
            }
            for v in versions
        ],
    }


@router.get("/{project_id}/versions/{vid}")
async def get_version(
    project_id: str,
    vid: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """获取指定版本的完整 DSL。"""
    from db.models import Project, ProjectVersion

    vid_uuid = safe_project_uuid(vid)
    if vid_uuid is None:
        raise HTTPException(status_code=422, detail="无效的版本 ID 格式")
    v = await session.get(ProjectVersion, vid_uuid)
    if v is None or str(v.project_id) != project_id:
        raise HTTPException(status_code=404, detail="Version not found")
    project = await session.get(Project, parse_project_id(project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    return {
        "id": str(v.id),
        "version": v.version,
        "change_summary": v.change_summary,
        "dsl": v.dsl_snapshot,
        "created_at": v.created_at.isoformat() if v.created_at else None,
        "is_current": v.id == project.current_version_id,
    }


@router.get("/{project_id}/versions/{vid}/diff")
async def diff_version(
    project_id: str,
    vid: str,
    to_version_id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_readonly_session),
) -> dict:
    """Compare one saved version with another version or the current project DSL."""
    from db.models import Project as ProjectModel
    from db.models import ProjectVersion

    source_uuid = safe_project_uuid(vid)
    if source_uuid is None:
        raise HTTPException(status_code=422, detail="无效的版本 ID 格式")
    source = await session.get(ProjectVersion, source_uuid)
    if source is None or str(source.project_id) != project_id:
        raise HTTPException(status_code=404, detail="Version not found")

    if to_version_id:
        target_uuid = safe_project_uuid(to_version_id)
        if target_uuid is None:
            raise HTTPException(status_code=422, detail="无效的目标版本 ID 格式")
        target = await session.get(ProjectVersion, target_uuid)
        if target is None or str(target.project_id) != project_id:
            raise HTTPException(status_code=404, detail="Target version not found")
        target_dsl = target.dsl_snapshot
        target_ref = {
            "type": "version",
            "id": str(target.id),
            "version": target.version,
        }
    else:
        project = await session.get(ProjectModel, parse_project_id(project_id))
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        target_dsl = project.dsl_snapshot
        target_ref = {"type": "current", "id": project_id}

    return {
        "from": {"type": "version", "id": str(source.id), "version": source.version},
        "to": target_ref,
        **diff_dsl_versions(source.dsl_snapshot, target_dsl),
    }


@router.post("/{project_id}/versions/{vid}/restore")
async def restore_version(
    project_id: str,
    vid: str,
    session: AsyncSession = Depends(get_session),
    _editor: Annotated[User | None, Depends(require_editor)] = None,
) -> dict:
    """恢复到指定版本（将 DSL 替换为该版本的快照）。"""
    from db.models import Project as ProjectModel
    from db.models import ProjectVersion

    project = await session.get(ProjectModel, parse_project_id(project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    vid_uuid = safe_project_uuid(vid)
    if vid_uuid is None:
        raise HTTPException(status_code=422, detail="无效的版本 ID 格式")
    v = await session.get(ProjectVersion, vid_uuid)
    if v is None or str(v.project_id) != project_id:
        raise HTTPException(status_code=404, detail="Version not found")

    # 恢复前先保存当前版本
    if project.dsl_snapshot:
        await save_version(project_id, project.dsl_snapshot, "恢复前自动存档", session)

    # 恢复（与存档在同一个事务中提交）
    project.dsl_snapshot = v.dsl_snapshot
    project.current_version_id = v.id

    # 同步重写 frames 表，避免表与 snapshot 漂移
    from services.project_persistence import persist_frames_to_table

    await persist_frames_to_table(
        project_id, (v.dsl_snapshot or {}).get("frames", []), session
    )

    await session.commit()

    logger.info("版本已恢复: project=%s version=%d", project_id, v.version)
    return {"restored_to_version": v.version, "id": str(v.id)}
