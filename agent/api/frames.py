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
from .deps import CurrentUser
from .ownership import get_owned_project

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["frames"])


@router.get("/{project_id}/frames")
async def list_frames(
    project_id: str,
    current_user: CurrentUser,
    version: int = 1,
    session: AsyncSession = Depends(get_readonly_session),
) -> dict:
    """获取项目的帧列表。

    帧表为编辑真源：优先返回 ``frames`` 表中的行；仅当表为空时回退到
    ``dsl_snapshot['frames']``（兼容尚未落表的历史项目）。
    """
    from db.models import Frame as FrameModel

    from sqlalchemy import select

    project = await get_owned_project(session, project_id, current_user.id)

    # DB frames 表优先（编辑真源，反映最新编辑/锁定状态）
    query = (
        select(FrameModel)
        .where(
            FrameModel.project_id == project.id,
            FrameModel.version == version,
        )
        .order_by(FrameModel.order_index)
    )
    result = await session.execute(query)
    frames = result.scalars().all()

    if frames:
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

    # 回退：DSL snapshot 中的帧数据（尚未落表的历史项目）
    if project.dsl_snapshot:
        snap_frames = project.dsl_snapshot.get("frames", [])
        if snap_frames:
            for f in snap_frames:
                if "id" not in f:
                    f["id"] = str(uuid.uuid4())
            return {"frames": snap_frames, "version": 1}

    return {"frames": [], "version": version}


@router.put("/{project_id}/frames/{fid}")
async def update_frame(
    project_id: str,
    fid: str,
    body: FrameUpdateRequest,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """编辑单帧内容。"""
    from db.models import Frame as FrameModel

    from sqlalchemy import select

    project = await get_owned_project(
        session, project_id, current_user.id, for_update=True
    )

    # 查找帧
    query = select(FrameModel).where(
        FrameModel.project_id == project.id,
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

    # 同步回 dsl_snapshot['frames']，保证「推演/导出」读到的 DSL 与编辑一致
    await _sync_frame_into_snapshot(session, project, fid, updates)

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
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """锁定或解锁帧。"""
    from db.models import Frame as FrameModel

    from sqlalchemy import select

    project = await get_owned_project(
        session, project_id, current_user.id, for_update=True
    )

    query = select(FrameModel).where(
        FrameModel.project_id == project.id,
        FrameModel.frame_id == fid,
    )
    result = await session.execute(query)
    frame = result.scalar_one_or_none()

    if frame is None:
        raise HTTPException(status_code=404, detail="Frame not found")

    frame.is_locked = body.is_locked
    await session.flush()

    # 同步锁定状态到 dsl_snapshot
    await _sync_frame_into_snapshot(session, project, fid, {"is_locked": body.is_locked})

    return {"id": str(frame.id), "is_locked": frame.is_locked}


async def _sync_frame_into_snapshot(
    session: AsyncSession,
    project,
    frame_id: str,
    fields: dict,
) -> None:
    """将单帧的字段变更同步回 project.dsl_snapshot['frames']（整体重赋值触发 JSONB 变更）。"""
    if not project.dsl_snapshot:
        return

    snap = dict(project.dsl_snapshot)
    frames = [dict(f) for f in snap.get("frames", [])]
    changed = False
    for f in frames:
        if f.get("frame_id") == frame_id:
            f.update(fields)
            changed = True
            break

    if changed:
        snap["frames"] = frames
        project.dsl_snapshot = snap
        await session.flush()
