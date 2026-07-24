"""版本管理 API 路由。

POST   /api/projects/{id}/versions                    保存当前版本
GET    /api/projects/{id}/versions                     版本列表
GET    /api/projects/{id}/versions/{vid}               获取指定版本
POST   /api/projects/{id}/versions/{vid}/restore       恢复到指定版本
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_session
from schema.project import CreateVersionRequest
from .deps import CurrentUser, parse_project_id, safe_project_uuid
from .ownership import get_owned_project

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

    from db.models import ProjectVersion

    # 获取当前最大版本号
    # NOTE: SELECT MAX + INSERT 在并发下有 TOCTOU 竞态，UniqueConstraint 兜底。
    # 教学工具场景并发度低，可接受；高并发场景应改用 SELECT ... FOR UPDATE。
    result = await session.execute(
        select(func.max(ProjectVersion.version))
        .where(ProjectVersion.project_id == parse_project_id(project_id))
    )
    max_ver = result.scalar() or 0

    version = ProjectVersion(
        id=uuid.uuid4(),
        project_id=parse_project_id(project_id),
        version=max_ver + 1,
        dsl_snapshot=dsl,
        change_summary=change_summary or f"Auto-saved at {datetime.now(timezone.utc).isoformat()}",
    )
    session.add(version)
    await session.flush()

    logger.info("版本已保存: project=%s version=%d", project_id, version.version)
    return {"version": version.version, "id": str(version.id)}


@router.post("/{project_id}/versions", status_code=201)
async def create_version(
    project_id: str,
    body: CreateVersionRequest,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """手动保存当前 DSL 为新版本。"""
    project = await get_owned_project(
        session, project_id, current_user.id, for_update=True
    )
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
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """获取项目的所有历史版本。"""
    from db.models import ProjectVersion

    project = await get_owned_project(session, project_id, current_user.id)

    query = (
        select(ProjectVersion)
        .where(ProjectVersion.project_id == project.id)
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
            }
            for v in versions
        ],
    }


@router.get("/{project_id}/versions/{vid}")
async def get_version(
    project_id: str,
    vid: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """获取指定版本的完整 DSL。"""
    from db.models import ProjectVersion

    project = await get_owned_project(session, project_id, current_user.id)

    vid_uuid = safe_project_uuid(vid)
    if vid_uuid is None:
        raise HTTPException(status_code=422, detail="无效的版本 ID 格式")
    v = await session.scalar(
        select(ProjectVersion).where(
            ProjectVersion.id == vid_uuid,
            ProjectVersion.project_id == project.id,
        )
    )
    if v is None:
        raise HTTPException(status_code=404, detail="Version not found")

    return {
        "id": str(v.id),
        "version": v.version,
        "change_summary": v.change_summary,
        "dsl": v.dsl_snapshot,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


@router.post("/{project_id}/versions/{vid}/restore")
async def restore_version(
    project_id: str,
    vid: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """恢复到指定版本（将 DSL 替换为该版本的快照）。"""
    from db.models import ProjectVersion

    project = await get_owned_project(
        session, project_id, current_user.id, for_update=True
    )

    vid_uuid = safe_project_uuid(vid)
    if vid_uuid is None:
        raise HTTPException(status_code=422, detail="无效的版本 ID 格式")
    v = await session.scalar(
        select(ProjectVersion).where(
            ProjectVersion.id == vid_uuid,
            ProjectVersion.project_id == project.id,
        )
    )
    if v is None:
        raise HTTPException(status_code=404, detail="Version not found")

    # 恢复前先保存当前版本
    if project.dsl_snapshot:
        await save_version(project_id, project.dsl_snapshot, "恢复前自动存档", session)

    # 恢复（与存档在同一个事务中提交）
    project.dsl_snapshot = v.dsl_snapshot

    # 同步重写 frames 表，避免表与 snapshot 漂移
    from services.project_persistence import persist_frames_to_table
    await persist_frames_to_table(
        project_id, (v.dsl_snapshot or {}).get("frames", []), session
    )

    await session.commit()

    logger.info("版本已恢复: project=%s version=%d", project_id, v.version)
    return {"restored_to_version": v.version, "id": str(v.id)}
