"""反馈 API 路由。

POST   /api/projects/{id}/feedback         提交反馈
GET    /api/projects/{id}/feedback          查询反馈列表
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_session
from schema.project import FeedbackRequest
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
) -> dict:
    """提交用户反馈，并触发反思修订。

    反馈类型：
    - rating: 评分 (1-5)，≤2 分触发 Quality 重新评估
    - correction: 纠错，关联到具体帧，触发局部重生成
    - suggestion: 建议，记录但不自动触发修订
    """
    from db.models import Feedback, Project as ProjectModel

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
    await session.flush()
    await session.commit()

    logger.info("反馈已持久化: id=%s | project=%s | frame=%s | type=%s | rating=%s",
                feedback.id, project_id, body.frame_id, body.type, body.rating)

    # 触发反思修订（后台任务，不阻塞 HTTP 响应）
    should_reflect = False
    if body.type == "correction" and body.frame_id:
        should_reflect = True
        logger.info("纠错反馈: 触发局部重生成 | frame=%s", body.frame_id)
    elif body.type == "rating" and body.rating and body.rating <= 2:
        should_reflect = True
        logger.info("低分反馈: 触发 Quality 重新评估 | rating=%d", body.rating)

    if should_reflect and project.dsl_snapshot:
        try:
            import asyncio
            # 不传 request 级 session —— 后台任务用独立 session
            asyncio.create_task(
                _trigger_reflection(project_id, pid, project.dsl_snapshot, feedback)
            )
            logger.info("反思修订已触发（后台）: project=%s", project_id)
        except Exception as exc:
            logger.warning("反思修订触发失败: %s（反馈已保存）", exc)

    return {"id": str(feedback.id)}


async def _trigger_reflection(
    project_id: str,
    pid,
    dsl: dict,
    feedback,
) -> None:
    """触发 Reflection Agent 根据反馈内容修正 DSL，并持久化结果。

    使用独立的 async_session（不依赖请求级 session，避免 ResourceClosedError）。
    """
    from agents.state import AgentState
    from agents.nodes import reflection_node
    from db.database import async_session_factory
    from db.models import Project as ProjectModel

    state: AgentState = {
        "project_id": project_id,
        "dsl": dsl,
        "reflection_count": 0,
        "revision_history": [],
        "user_feedback": {
            "frame_id": str(feedback.frame_id) if feedback.frame_id else None,
            "type": feedback.type,
            "content": feedback.content,
            "rating": feedback.rating,
        },
        "quality_report": {
            "overall_score": 0.5,
            "is_blocking": True,
        },
    }

    try:
        result = await reflection_node(state)
        revised_dsl = result.get("dsl", dsl)
        logger.info("Reflection 完成: modified=%d",
                    len(result.get("revision_history", [])))

        # 持久化修订结果（独立 session）
        async with async_session_factory() as bg_session:
            project = await bg_session.get(ProjectModel, pid)
            if project and revised_dsl != project.dsl_snapshot:
                project.dsl_snapshot = revised_dsl
                await bg_session.commit()
                logger.info("修订 DSL 已保存: project=%s", project_id)

            # 仅在成功时标记 resolved
            feedback.resolved = True
            bg_session.add(feedback)
            await bg_session.commit()
    except Exception as exc:
        logger.exception("Reflection 修订失败: %s", exc)
