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
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_session, get_readonly_session
from schema.project import ProjectCreateRequest
from .deps import CurrentUser
from .ownership import get_owned_project

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", status_code=201)
async def create_project(
    body: ProjectCreateRequest,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """创建推演项目。"""
    from db.models import Project, SourceMaterial

    material_ids_raw = body.constraints.get("material_ids", [])
    if not isinstance(material_ids_raw, list):
        raise HTTPException(status_code=400, detail="material_ids must be a list")

    try:
        material_ids = [uuid.UUID(str(material_id)) for material_id in material_ids_raw]
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(status_code=400, detail="Invalid material ID")

    materials = []
    if material_ids:
        materials = list(
            (
                await session.execute(
                    select(SourceMaterial).where(
                        SourceMaterial.id.in_(material_ids),
                        SourceMaterial.owner_id == current_user.id,
                    )
                )
            ).scalars()
        )
        if len(materials) != len(set(material_ids)):
            raise HTTPException(status_code=400, detail="Invalid material ID")

    project = Project(
        id=uuid.uuid4(),
        title=body.title,
        audience=body.audience,
        difficulty=body.difficulty,
        owner_id=current_user.id,
        status="draft",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    session.add(project)
    for material in materials:
        material.project_id = project.id
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
    current_user: CurrentUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    session: AsyncSession = Depends(get_readonly_session),
) -> dict:
    """获取项目列表。"""
    from db.models import Project

    count_query = select(func.count(Project.id)).where(Project.owner_id == current_user.id)
    items_query = (
        select(Project)
        .where(Project.owner_id == current_user.id)
        .order_by(Project.updated_at.desc())
    )

    if status:
        count_query = count_query.where(Project.status == status)
        items_query = items_query.where(Project.status == status)

    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    items_query = items_query.offset((page - 1) * page_size).limit(page_size)
    items_result = await session.execute(items_query)
    projects = items_result.scalars().all()

    return {
        "items": [
            {
                "id": str(p.id),
                "title": p.title,
                "topic": p.topic,
                "difficulty": p.difficulty,
                "status": p.status,
                "frame_count": 0,  # 需要额外 count 查询
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
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_readonly_session),
) -> dict:
    """获取项目详情（含最新 DSL）。"""
    from db.models import Frame

    project = await get_owned_project(session, project_id, current_user.id)

    # 获取帧数量
    frame_count_result = await session.execute(
        select(func.count(Frame.id)).where(
            Frame.project_id == project.id,
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
        "frame_count": frame_count,
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
    }


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> None:
    """删除项目（级联删除帧/参数/版本等关联记录）。"""
    project = await get_owned_project(
        session, project_id, current_user.id, for_update=True
    )

    await session.delete(project)
    logger.info("项目删除: id=%s", project_id)
