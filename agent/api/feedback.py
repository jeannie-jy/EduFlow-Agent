"""反馈 API 路由。

POST   /api/projects/{id}/feedback         提交反馈
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_session
from .deps import parse_project_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["feedback"])


@router.post("/{project_id}/feedback", status_code=201)
async def submit_feedback(
    project_id: str,
    body: dict,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """提交用户反馈。

    反馈类型：
    - rating: 评分 (1-5)
    - correction: 纠错
    - suggestion: 建议
    """
    from db.models import Project as ProjectModel

    project = await session.get(ProjectModel, parse_project_id(project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    frame_id = body.get("frame_id")
    feedback_type = body.get("type", "correction")
    content = body.get("content", "")
    rating = body.get("rating")

    # 验证 rating
    if feedback_type == "rating" and (rating is None or not (1 <= rating <= 5)):
        raise HTTPException(status_code=422, detail="rating must be 1-5 when type=rating")

    # 验证 content
    if feedback_type != "rating" and not content.strip():
        raise HTTPException(status_code=422, detail="content is required")

    logger.info(
        "反馈提交: project=%s | frame=%s | type=%s | rating=%s",
        project_id, frame_id, feedback_type, rating,
    )

    # TODO: 持久化到 feedback 表，并触发反思修订
    return {"id": str(uuid.uuid4())}
