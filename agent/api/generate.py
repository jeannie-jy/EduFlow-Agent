"""生成流程 API 路由。

POST   /api/projects/{id}/generate          启动生成
GET    /api/projects/{id}/generate/stream    SSE 进度流
POST   /api/projects/{id}/regenerate        局部重生成
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from db.database import get_session
from services.generate_service import run_generation_stream, resume_generation_stream, run_regenerate_stream
from schema.project import GenerateRequest, RegenerateRequest, RejectPlanRequest, ApprovePlanResponse
from .deps import CurrentUser
from .ownership import get_owned_project

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["generate"])


@router.post("/{project_id}/generate", status_code=202)
async def start_generation(
    project_id: str,
    body: GenerateRequest,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """启动生成流程。返回 SSE 流地址。"""
    project = await get_owned_project(
        session, project_id, current_user.id, for_update=True
    )

    # 获取输入内容
    input_content = ""
    constraints = {}
    if project.dsl_snapshot:
        input_content = project.dsl_snapshot.get("input_content", "")
        constraints = project.dsl_snapshot.get("constraints", {})

    # 更新状态；记录本次生成模式供 GET stream 读取（stream 无 body）
    project.status = "planning"
    snap = dict(project.dsl_snapshot or {})
    snap["_pending_action"] = body.action
    project.dsl_snapshot = snap

    logger.info("生成启动: project=%s | action=%s", project_id, body.action)

    return {
        "stream_url": f"/api/projects/{project_id}/generate/stream",
    }


@router.get("/{project_id}/generate/stream")
async def generation_stream(
    project_id: str,
    request: Request,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """SSE 流式推送生成进度。"""
    project = await get_owned_project(session, project_id, current_user.id)

    input_content = ""
    constraints = {}
    action = "full"
    if project.dsl_snapshot:
        input_content = project.dsl_snapshot.get("input_content", project.title)
        constraints = project.dsl_snapshot.get("constraints", {})
        action = project.dsl_snapshot.get("_pending_action", "full")

    # file_upload 素材接线：载入已上传素材的解析文本供 Planner 使用
    materials: list[dict] = []
    material_ids = constraints.get("material_ids", []) if isinstance(constraints, dict) else []
    if material_ids:
        from api.materials import parse_material_file
        for mid in material_ids:
            try:
                parsed = parse_material_file(str(mid))
            except Exception as exc:
                logger.warning("素材解析失败 material=%s: %s", mid, exc)
                parsed = None
            if parsed and parsed.get("raw_text"):
                materials.append({
                    "material_id": str(mid),
                    "content_text": parsed["raw_text"],
                    "topics": parsed.get("topics", []),
                })
        logger.info("生成载入素材: project=%s | count=%d", project_id, len(materials))

    async def event_generator():
        async for sse_chunk in run_generation_stream(
            project_id=project_id,
            user_input=input_content,
            action=action,
            constraints=constraints,
            materials=materials,
        ):
            # 检查客户端是否断开
            if await request.is_disconnected():
                break
            yield sse_chunk

    return EventSourceResponse(event_generator())


@router.get("/{project_id}/generate/resume/stream")
async def generation_resume_stream(
    project_id: str,
    request: Request,
    current_user: CurrentUser,
    decision: str = "approve",
    feedback: str = "",
    session: AsyncSession = Depends(get_session),
):
    """从 HITL 中断点恢复生成流程的 SSE 流。

    Query:
        decision: approve | reject
        feedback: 拒绝时的修改意见
    """
    await get_owned_project(session, project_id, current_user.id)

    resume_value = (
        {"action": "reject", "feedback": feedback}
        if decision == "reject"
        else {"action": "approve"}
    )

    async def event_generator():
        async for sse_chunk in resume_generation_stream(project_id, resume_value):
            if await request.is_disconnected():
                break
            yield sse_chunk

    return EventSourceResponse(event_generator())


@router.post("/{project_id}/regenerate", status_code=202)
async def regenerate_frames(
    project_id: str,
    body: RegenerateRequest,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """局部重生成指定帧范围。

    从 DB frames 表读取锁定帧、从 dsl_snapshot 读取已有规划/知识图谱，
    跳过 Planner+Knowledge，直接驱动 Coder→Quality→Reflection 循环。
    """
    await get_owned_project(session, project_id, current_user.id, for_update=True)

    scope = body.scope

    logger.info("重生成: project=%s | scope=%s", project_id, scope.get("type", "unknown"))

    return {
        "stream_url": f"/api/projects/{project_id}/generate/regenerate/stream",
    }


@router.get("/{project_id}/generate/regenerate/stream")
async def regenerate_stream(
    project_id: str,
    request: Request,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """局部重生成的 SSE 进度流（跳过 Planner+Knowledge，直接到 Coder）。"""
    await get_owned_project(session, project_id, current_user.id)

    async def event_generator():
        async for sse_chunk in run_regenerate_stream(
            project_id=project_id,
            scope={"type": "from_frame"},
        ):
            if await request.is_disconnected():
                break
            yield sse_chunk

    return EventSourceResponse(event_generator())


@router.post("/{project_id}/generate/approve", status_code=200)
async def approve_plan(
    project_id: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> ApprovePlanResponse:
    """批准教学计划，清除 pending_approval 并继续生成流程。

    前端调用此端点后，应重新连接 SSE stream 继续接收后续进度。
    """
    project = await get_owned_project(
        session, project_id, current_user.id, for_update=True
    )

    # 清除审批标记，更新状态（整体重赋值以触发 JSONB 变更检测）
    if project.dsl_snapshot:
        snap = dict(project.dsl_snapshot)
        snap.pop("pending_approval", None)
        project.dsl_snapshot = snap
    project.status = "generating"

    logger.info("教学计划已批准: project=%s", project_id)

    # 前端应连接 resume 流从中断点继续（不重跑 Planner）
    return ApprovePlanResponse(
        stream_url=f"/api/projects/{project_id}/generate/resume/stream?decision=approve",
    )


@router.post("/{project_id}/generate/reject", status_code=200)
async def reject_plan(
    project_id: str,
    body: RejectPlanRequest,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> ApprovePlanResponse:
    """拒绝教学计划，携带修改意见重新规划。

    将用户反馈写入 project DSL snapshot，前端可重新触发生成流程。
    """
    project = await get_owned_project(
        session, project_id, current_user.id, for_update=True
    )

    # 记录拒绝反馈（整体重赋值以触发 JSONB 变更检测）
    if project.dsl_snapshot:
        snap = dict(project.dsl_snapshot)
        snap["approval_feedback"] = body.feedback
        snap.pop("pending_approval", None)
        project.dsl_snapshot = snap
    project.status = "draft"

    logger.info("教学计划被拒绝: project=%s | feedback=%s", project_id, body.feedback[:100])

    # 连接 resume 流注入拒绝决定，让图正常消费中断点后结束
    from urllib.parse import quote
    return ApprovePlanResponse(
        stream_url=(
            f"/api/projects/{project_id}/generate/resume/stream"
            f"?decision=reject&feedback={quote(body.feedback)}"
        ),
    )
