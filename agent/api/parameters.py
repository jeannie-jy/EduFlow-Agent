"""参数 API 路由。

GET    /api/projects/{id}/parameters      参数列表
POST   /api/projects/{id}/recompute       参数变更触发重算
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_session, get_readonly_session
from schema.project import RecomputeRequest
from .deps import parse_project_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["parameters"])


@router.get("/{project_id}/parameters")
async def list_parameters(
    project_id: str,
    session: AsyncSession = Depends(get_readonly_session),
) -> dict:
    """获取项目的参数列表。"""
    # 优先从 DSL snapshot 获取
    from db.models import Project as ProjectModel
    project = await session.get(ProjectModel, parse_project_id(project_id))
    if project and project.dsl_snapshot:
        params = project.dsl_snapshot.get("parameters", [])
        if params:
            for p in params:
                if "id" not in p:
                    p["id"] = str(uuid.uuid4())
            return {"parameters": params}

    # 从 DB 查询
    from db.models import ParameterModel

    from sqlalchemy import select

    query = select(ParameterModel).where(
        ParameterModel.project_id == parse_project_id(project_id)
    )
    result = await session.execute(query)
    params = result.scalars().all()

    return {
        "parameters": [
            {
                "id": str(p.id),
                "key": p.key,
                "label": p.label,
                "param_type": p.param_type,
                "default_value": p.default_value,
                "current_value": p.current_value,
                "constraints": p.constraints or {},
                "recompute_scope": p.recompute_scope,
            }
            for p in params
        ],
    }


@router.post("/{project_id}/recompute", status_code=202)
async def recompute_project(
    project_id: str,
    body: RecomputeRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """参数变更触发状态重算。"""
    from db.models import Project as ProjectModel

    project = await session.get(ProjectModel, parse_project_id(project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    changed_params = body.changed_params

    logger.info("重算: project=%s | changed_keys=%s", project_id, list(changed_params.keys()))

    # 更新参数值
    from db.models import ParameterModel

    from sqlalchemy import select, update

    for key, value in changed_params.items():
        await session.execute(
            update(ParameterModel)
            .where(
                ParameterModel.project_id == parse_project_id(project_id),
                ParameterModel.key == key,
            )
            .values(current_value=value)
        )

    # 触发重新生成
    return {
        "stream_url": f"/api/projects/{project_id}/generate/stream",
    }
