"""反馈 API 路由。

POST   /api/projects/{id}/feedback         提交反馈
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_session
from schema.project import FeedbackRequest
from .deps import parse_project_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["feedback"])


@router.post("/{project_id}/feedback", status_code=201)
async def submit_feedback(
    project_id: str,
    body: FeedbackRequest,
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

    logger.info(
        "反馈提交: project=%s | frame=%s | type=%s | rating=%s",
        project_id, body.frame_id, body.type, body.rating,
    )

    # TODO: 持久化到 feedback 表，并触发反思修订
    return {"id": str(uuid.uuid4())}
