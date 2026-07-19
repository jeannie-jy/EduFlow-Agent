"""生成流程 API 路由。

POST   /api/projects/{id}/generate          启动生成
GET    /api/projects/{id}/generate/stream    SSE 进度流
POST   /api/projects/{id}/regenerate        局部重生成
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from db.database import get_session
from services.generate_service import run_generation_stream
from schema.project import GenerateRequest
from .deps import parse_project_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["generate"])


@router.post("/{project_id}/generate", status_code=202)
async def start_generation(
    project_id: str,
    body: GenerateRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """启动生成流程。返回 SSE 流地址。"""
    from db.models import Project as ProjectModel

    # 验证项目存在
    project = await session.get(ProjectModel, parse_project_id(project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # 获取输入内容
    input_content = ""
    constraints = {}
    if project.dsl_snapshot:
        input_content = project.dsl_snapshot.get("input_content", "")
        constraints = project.dsl_snapshot.get("constraints", {})

    # 更新状态
    project.status = "planning"

    logger.info("生成启动: project=%s | action=%s", project_id, body.get("action", "full"))

    return {
        "stream_url": f"/api/projects/{project_id}/generate/stream",
    }


@router.get("/{project_id}/generate/stream")
async def generation_stream(
    project_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """SSE 流式推送生成进度。"""
    from db.models import Project as ProjectModel

    # 获取项目信息
    project = await session.get(ProjectModel, parse_project_id(project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    input_content = ""
    constraints = {}
    if project.dsl_snapshot:
        input_content = project.dsl_snapshot.get("input_content", project.title)
        constraints = project.dsl_snapshot.get("constraints", {})

    async def event_generator():
        async for sse_chunk in run_generation_stream(
            project_id=project_id,
            user_input=input_content,
            constraints=constraints,
        ):
            # 检查客户端是否断开
            if await request.is_disconnected():
                break
            yield sse_chunk

    return EventSourceResponse(event_generator())


@router.post("/{project_id}/regenerate", status_code=202)
async def regenerate_frames(
    project_id: str,
    body: dict,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """局部重生成指定帧范围。"""
    from db.models import Project as ProjectModel

    project = await session.get(ProjectModel, parse_project_id(project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    scope = body.get("scope", {})

    logger.info("重生成: project=%s | scope=%s", project_id, scope.get("type", "unknown"))

    return {
        "stream_url": f"/api/projects/{project_id}/generate/stream",
    }
