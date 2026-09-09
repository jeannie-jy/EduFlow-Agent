"""反馈 API 路由。

POST   /api/projects/{id}/feedback         提交反馈
GET    /api/projects/{id}/feedback          查询反馈列表
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_session
from db.models import User
from schema.project import FeedbackRequest
from services.audit import record_audit
from .auth import get_current_user
from .deps import parse_project_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["feedback"])


@router.get("/{project_id}/feedback")
async def list_feedback(
    project_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """查询项目的反馈列表。"""
    from db.models import Feedback, Project as ProjectModel

    project = await session.get(ProjectModel, parse_project_id(project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    query = (
        select(Feedback)
        .where(Feedback.project_id == parse_project_id(project_id))
        .order_by(Feedback.created_at.desc())
    )
    result = await session.execute(query)
    items = result.scalars().all()

    return {
        "items": [
            {
                "id": str(f.id),
                "frame_id": str(f.frame_id) if f.frame_id else None,
                "type": f.type,
                "content": f.content,
                "rating": f.rating,
                "resolved": f.resolved,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in items
        ],
    }


@router.post("/{project_id}/feedback", status_code=201)
async def submit_feedback(
    project_id: str,
    body: FeedbackRequest,
    session: AsyncSession = Depends(get_session),
    current_user: Annotated[User | None, Depends(get_current_user)] = None,
) -> dict:
    """提交用户反馈，并触发反思修订。

    反馈类型：
    - rating: 评分 (1-5)，≤2 分触发 Quality 重新评估
    - correction: 纠错，关联到具体帧，触发局部重生成
    - suggestion: 建议，记录但不自动触发修订
    """
    from db.models import BackgroundJob, Feedback, Project as ProjectModel

    pid = parse_project_id(project_id)
    project = await session.get(ProjectModel, pid)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # 持久化反馈。body.frame_id 是 DSL 帧 ID（如 "f_001"），需映射到 frames 表的行 UUID；
    # 之前误用 safe_project_uuid 解析，DSL 帧 ID 永远解析失败 → 关联丢失。
    frame_row_id = None
    if body.frame_id:
        from db.models import Frame

        frame_query = select(Frame.id).where(
            Frame.project_id == pid,
            Frame.frame_id == body.frame_id,
        ).limit(1)
        row = (await session.execute(frame_query)).first()
        if row is not None:
            frame_row_id = row[0]
        else:
            logger.warning("反馈关联的帧不存在，frame 关联置空: frame=%s", body.frame_id)

    feedback = Feedback(
        id=uuid.uuid4(),
        project_id=pid,
        frame_id=frame_row_id,
        type=body.type,
        content=body.content,
        rating=body.rating,
    )
    session.add(feedback)

    # 需要 Agent 修订时与反馈在同一事务中写入持久化队列；API 进程
    # 不再持有易丢失的 asyncio.create_task。
    should_reflect = False
    if body.type == "correction" and body.frame_id:
        should_reflect = True
        logger.info("纠错反馈: 触发局部重生成 | frame=%s", body.frame_id)
    elif body.type == "rating" and body.rating and body.rating <= 2:
        should_reflect = True
        logger.info("低分反馈: 触发 Quality 重新评估 | rating=%d", body.rating)

    reflection_job_id = None
    if should_reflect and project.dsl_snapshot:
        reflection_job_id = uuid.uuid4()
        session.add(BackgroundJob(
            id=reflection_job_id,
            project_id=pid,
            owner_id=current_user.id if current_user is not None else None,
            kind="feedback_reflection",
            idempotency_key=str(feedback.id),
            payload={
                "feedback_id": str(feedback.id),
                "frame_id": body.frame_id,
            },
            status="queued",
        ))

    record_audit(
        session,
        action="feedback.create",
        resource_type="feedback",
        resource_id=str(feedback.id),
        actor_id=current_user.id if current_user is not None else None,
        details={"type": body.type, "reflection_queued": reflection_job_id is not None},
    )
    await session.flush()
    await session.commit()

    logger.info(
        "反馈已持久化: id=%s | project=%s | reflection_job=%s",
        feedback.id,
        project_id,
        reflection_job_id,
    )
    return {
        "id": str(feedback.id),
        "reflection_job_id": str(reflection_job_id) if reflection_job_id else None,
    }
