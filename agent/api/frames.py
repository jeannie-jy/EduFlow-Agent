"""帧 API 路由。

GET    /api/projects/{id}/frames            帧列表
PUT    /api/projects/{id}/frames/{fid}      编辑单帧
POST   /api/projects/{id}/frames/{fid}/lock 锁定/解锁帧
"""

from __future__ import annotations

import hashlib
import json
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
    """获取项目的帧列表。

    帧表为编辑真源：优先返回 ``frames`` 表中的行；仅当表为空时回退到
    ``dsl_snapshot['frames']``（兼容尚未落表的历史项目）。
    """
    from db.models import Frame as FrameModel

    from sqlalchemy import select

    # DB frames 表优先（编辑真源，反映最新编辑/锁定状态）
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
    from db.models import Project as ProjectModel
    project = await session.get(ProjectModel, parse_project_id(project_id))
    if project and project.dsl_snapshot:
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
        # 历史项目可能只有 JSON 快照而没有 frames 表记录，仍允许直接编辑快照。
        from db.models import Project as ProjectModel
        project = await session.get(ProjectModel, parse_project_id(project_id))
        snapshot_frames = (project.dsl_snapshot or {}).get("frames", []) if project else []
        snapshot_frame = next((f for f in snapshot_frames if f.get("frame_id") == fid), None)
        if snapshot_frame is None:
            raise HTTPException(status_code=404, detail="Frame not found")
        if snapshot_frame.get("is_locked"):
            raise HTTPException(status_code=409, detail="Frame is locked")
        updates = body.model_dump(exclude_none=True)
        await _sync_frame_into_snapshot(session, project_id, fid, updates)
        logger.info("历史帧编辑: project=%s | frame=%s", project_id, fid)
        return {"id": str(snapshot_frame.get("id", fid)), "updated_at": None}

    if frame.is_locked:
        raise HTTPException(status_code=409, detail="Frame is locked")

    # 更新字段（只更新显式传入的非 None 字段）
    updates = body.model_dump(exclude_none=True)
    for field, value in updates.items():
        setattr(frame, field, value)

    await session.flush()

    # 同步回 dsl_snapshot['frames']，保证「推演/导出」读到的 DSL 与编辑一致
    await _sync_frame_into_snapshot(session, project_id, fid, updates)

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
        from db.models import Project as ProjectModel
        project = await session.get(ProjectModel, parse_project_id(project_id))
        snapshot_frames = (project.dsl_snapshot or {}).get("frames", []) if project else []
        snapshot_frame = next((f for f in snapshot_frames if f.get("frame_id") == fid), None)
        if snapshot_frame is None:
            raise HTTPException(status_code=404, detail="Frame not found")
        await _sync_frame_into_snapshot(
            session, project_id, fid, {"is_locked": body.is_locked}
        )
        return {"id": str(snapshot_frame.get("id", fid)), "is_locked": body.is_locked}

    frame.is_locked = body.is_locked
    await session.flush()

    # 同步锁定状态到 dsl_snapshot
    await _sync_frame_into_snapshot(session, project_id, fid, {"is_locked": body.is_locked})

    return {"id": str(frame.id), "is_locked": frame.is_locked}


async def _sync_frame_into_snapshot(
    session: AsyncSession,
    project_id: str,
    frame_id: str,
    fields: dict,
) -> None:
    """将单帧的字段变更同步回 project.dsl_snapshot['frames']（整体重赋值触发 JSONB 变更）。"""
    from db.models import Project as ProjectModel

    project = await session.get(ProjectModel, parse_project_id(project_id))
    if project is None or not project.dsl_snapshot:
        return

    snap = dict(project.dsl_snapshot)
    def update_frames(frame_values: list) -> tuple[list, bool]:
        copied = [dict(f) for f in frame_values]
        for frame in copied:
            if frame.get("frame_id") == frame_id:
                frame.update(fields)
                return copied, True
        return copied, False

    frames, changed = update_frames(snap.get("frames", []))
    if changed:
        snap["frames"] = frames

    # 成果工作台读取 module_outputs.frames；同步该副本，避免刷新后编辑回退。
    module_outputs = dict(snap.get("module_outputs", {}))
    frames_output = dict(module_outputs.get("frames", {}))
    module_frames, module_changed = update_frames(frames_output.get("frames", []))
    if module_changed:
        frames_output["frames"] = module_frames
        if set(fields) - {"is_locked"}:
            version_payload = json.dumps(
                module_frames, ensure_ascii=False, sort_keys=True, default=str
            ).encode("utf-8")
            frames_output["artifact_version"] = hashlib.sha256(version_payload).hexdigest()[:12]
        module_outputs["frames"] = frames_output
        snap["module_outputs"] = module_outputs

    if changed and set(fields) - {"is_locked"}:
        version_payload = json.dumps(
            frames, ensure_ascii=False, sort_keys=True, default=str
        ).encode("utf-8")
        snap["artifact_version"] = hashlib.sha256(version_payload).hexdigest()[:12]

    if changed or module_changed:
        project.dsl_snapshot = snap
        await session.flush()
