"""帧 API 路由。

GET    /api/projects/{id}/frames            帧列表
PUT    /api/projects/{id}/frames/{fid}      编辑单帧
POST   /api/projects/{id}/frames/{fid}/lock 锁定/解锁帧
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_session, get_readonly_session
from schema.project import FrameUpdateRequest, FrameLockRequest
from .deps import parse_project_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["frames"])


@router.get("/{project_id}/frames")
async def list_frames(
    project_id: str,
    version: int = 1,
    session: AsyncSession = Depends(get_readonly_session),
) -> dict:
    """获取项目的帧列表。"""
    from db.models import Frame as FrameModel

    from sqlalchemy import select

    # 若 DSL snapshot 中有帧数据，优先返回
    from db.models import Project as ProjectModel
    project = await session.get(ProjectModel, parse_project_id(project_id))
    if project and project.dsl_snapshot:
        frames = project.dsl_snapshot.get("frames", [])
        if frames:
            # 补充 id 字段
            for i, f in enumerate(frames):
                if "id" not in f:
                    f["id"] = str(uuid.uuid4())
            return {"frames": frames, "version": 1}

    # DB 中查询
    query = (
        select(FrameModel)
        .where(
            FrameModel.project_id == parse_project_id(project_id),
            FrameModel.version == version,
        )
        .order_by(FrameModel.order_index)
    )
    result = await session.execute(query)
    frames = result.scalars().all()

    return {
        "frames": [
            {
                "id": str(f.id),
                "frame_id": f.frame_id,
                "order_index": f.order_index,
                "title": f.title or "",
                "narration": f.narration or "",
                "visual_objects": f.visual_objects or [],
                "state_snapshot": f.state_snapshot or {},
                "animations": f.animations or [],
                "interaction_hooks": f.interaction_hooks or [],
                "quality_status": f.quality_status,
                "is_locked": f.is_locked,
            }
            for f in frames
        ],
        "version": version,
    }


@router.put("/{project_id}/frames/{fid}")
async def update_frame(
    project_id: str,
    fid: str,
    body: FrameUpdateRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """编辑单帧内容。"""
    from db.models import Frame as FrameModel

    from sqlalchemy import select

    # 查找帧
    query = select(FrameModel).where(
        FrameModel.project_id == parse_project_id(project_id),
        FrameModel.frame_id == fid,
    )
    result = await session.execute(query)
    frame = result.scalar_one_or_none()

    if frame is None:
        raise HTTPException(status_code=404, detail="Frame not found")

    if frame.is_locked:
        raise HTTPException(status_code=409, detail="Frame is locked")

    # 更新字段（只更新显式传入的非 None 字段）
    updates = body.model_dump(exclude_none=True)
    for field, value in updates.items():
        setattr(frame, field, value)

    await session.flush()

    logger.info("帧编辑: project=%s | frame=%s", project_id, fid)

    return {
        "id": str(frame.id),
        "updated_at": frame.updated_at.isoformat() if frame.updated_at else None,
    }


@router.post("/{project_id}/frames/{fid}/lock")
async def lock_frame(
    project_id: str,
    fid: str,
    body: FrameLockRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """锁定或解锁帧。"""
    from db.models import Frame as FrameModel

    from sqlalchemy import select

    query = select(FrameModel).where(
        FrameModel.project_id == parse_project_id(project_id),
        FrameModel.frame_id == fid,
    )
    result = await session.execute(query)
    frame = result.scalar_one_or_none()

    if frame is None:
        raise HTTPException(status_code=404, detail="Frame not found")

    frame.is_locked = body.is_locked
    await session.flush()

    return {"id": str(frame.id), "is_locked": frame.is_locked}
