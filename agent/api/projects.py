"""项目 CRUD API 路由。

POST   /api/projects                  创建项目
GET    /api/projects                  项目列表
GET    /api/projects/{id}             项目详情
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_session, get_readonly_session
from schema.project import ProjectCreateRequest
from .deps import parse_project_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", status_code=201)
async def create_project(
    body: ProjectCreateRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """创建推演项目。"""
    from db.models import Project

    project = Project(
        id=uuid.uuid4(),
        title=body.title,
        audience=body.audience,
        difficulty=body.difficulty,
        status="draft",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    session.add(project)
    await session.flush()

    # 存储用户输入到 DSL snapshot
    project.dsl_snapshot = {
        "input_content": body.input_content,
        "input_type": body.input_type,
        "constraints": body.constraints,
    }

    logger.info("项目创建: id=%s | title=%s", project.id, project.title)

    return {
        "id": str(project.id),
        "title": project.title,
        "status": project.status,
        "created_at": project.created_at.isoformat() if project.created_at else None,
    }


@router.get("")
async def list_projects(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    session: AsyncSession = Depends(get_readonly_session),
) -> dict:
    """获取项目列表。"""
    from db.models import Project

    count_query = select(func.count(Project.id))
    items_query = select(Project).order_by(Project.updated_at.desc())

    if status:
        count_query = count_query.where(Project.status == status)
        items_query = items_query.where(Project.status == status)

    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    items_query = items_query.offset((page - 1) * page_size).limit(page_size)
    items_result = await session.execute(items_query)
    projects = items_result.scalars().all()

    # 批量统计每个项目的帧数（分批查询避免 SQL IN 子句过大）
    from db.models import Frame
    project_ids = [p.id for p in projects]
    frame_counts: dict[uuid.UUID, int] = {}
    if project_ids:
        batch_size = 200
        for i in range(0, len(project_ids), batch_size):
            batch = project_ids[i:i + batch_size]
            count_query = (
                select(Frame.project_id, func.count(Frame.id))
                .where(Frame.project_id.in_(batch), Frame.version == 1)
                .group_by(Frame.project_id)
            )
            count_result = await session.execute(count_query)
            frame_counts.update({row[0]: row[1] for row in count_result.all()})

    return {
        "items": [
            {
                "id": str(p.id),
                "title": p.title,
                "topic": p.topic,
                "difficulty": p.difficulty,
                "status": p.status,
                "frame_count": frame_counts.get(p.id, 0),
                "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            }
            for p in projects
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{project_id}")
async def get_project(
    project_id: str,
    session: AsyncSession = Depends(get_readonly_session),
) -> dict:
    """获取项目详情（含最新 DSL）。"""
    from db.models import Project, Frame

    project = await session.get(Project, parse_project_id(project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # 获取帧数量
    frame_count_result = await session.execute(
        select(func.count(Frame.id)).where(
            Frame.project_id == parse_project_id(project_id),
            Frame.version == 1,
        )
    )
    frame_count = frame_count_result.scalar() or 0

    return {
        "id": str(project.id),
        "title": project.title,
        "status": project.status,
        "audience": project.audience,
        "difficulty": project.difficulty,
        "teaching_plan": project.dsl_snapshot.get("teaching_plan") if project.dsl_snapshot else None,
        "knowledge_graph": project.dsl_snapshot.get("knowledge_graph") if project.dsl_snapshot else None,
        "dsl": project.dsl_snapshot,
        "quality_report": project.dsl_snapshot.get("quality_report") if project.dsl_snapshot else None,
        "module_outputs": project.dsl_snapshot.get("module_outputs") if project.dsl_snapshot else None,
        "selected_modules": project.dsl_snapshot.get("selected_modules") if project.dsl_snapshot else None,
        "frame_count": frame_count,
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
    }


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """删除项目（级联删除帧/参数/版本等关联记录）。"""
    from db.models import Project

    project = await session.get(Project, parse_project_id(project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    await session.delete(project)
    logger.info("项目删除: id=%s", project_id)
