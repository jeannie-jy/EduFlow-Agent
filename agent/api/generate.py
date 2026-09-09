"""生成流程 API 路由。

POST   /api/projects/{id}/generate             启动生成
GET    /api/projects/{id}/generate/stream       SSE 进度流
POST   /api/projects/{id}/regenerate           局部重生成
GET    /api/projects/{id}/generate/modules     获取可用模块列表
POST   /api/projects/{id}/generate/modules     提交模块选择开始生成
GET    /api/projects/{id}/generate/modules/stream 模块生成 SSE 流
"""

from __future__ import annotations

import json
import logging
import statistics
import uuid
from typing import Annotated
from urllib.parse import urlencode

from db.database import get_session
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from generators.registry import get_generator, list_generators
from schema.project import (
    ApprovePlanRequest,
    ApprovePlanResponse,
    GenerateRequest,
    ModuleCostEstimateResponse,
    ModuleInfo,
    ModuleListResponse,
    ModuleSelectRequest,
    RegenerateRequest,
    RejectPlanRequest,
)
from services.generate_service import (
    resume_generation_stream,
    run_generation_stream,
    run_modules_stream,
    run_regenerate_stream,
    with_sse_metadata,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from .auth import get_current_user, require_editor
from .deps import parse_project_id

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/projects",
    tags=["generate"],
    dependencies=[Depends(require_editor)],
)


async def _estimate_module_cost(
    session: AsyncSession, project_id: str, requested_count: int
) -> ModuleCostEstimateResponse:
    """Estimate from recent successful, non-zero module-node traces."""
    from config import get_settings
    from db.models import WorkflowNodeRun, WorkflowRun
    from sqlalchemy import select

    rows = (
        await session.execute(
            select(WorkflowNodeRun)
            .join(WorkflowRun, WorkflowNodeRun.workflow_run_id == WorkflowRun.id)
            .where(
                WorkflowRun.project_id == parse_project_id(project_id),
                WorkflowNodeRun.node_name == "modules",
                WorkflowNodeRun.status == "succeeded",
            )
            .order_by(WorkflowNodeRun.started_at.desc())
            .limit(100)
        )
    ).scalars().all()
    unit_costs: list[float] = []
    for row in rows:
        attributes = row.attributes if isinstance(row.attributes, dict) else {}
        module_count = attributes.get("module_count")
        cost = float(row.estimated_cost_usd or 0)
        if isinstance(module_count, int) and module_count > 0 and cost > 0:
            unit_costs.append(cost / module_count)

    settings = get_settings()
    estimate = (
        round(statistics.median(unit_costs) * requested_count, 8)
        if unit_costs
        else None
    )
    return ModuleCostEstimateResponse(
        available=estimate is not None,
        requested_module_count=requested_count,
        estimated_cost_usd=estimate,
        sample_count=len(unit_costs),
        method="historical_median_per_module" if unit_costs else "unavailable",
        hard_limit_cost_usd=settings.llm_request_max_cost_usd,
        hard_limit_tokens=settings.llm_request_max_tokens,
    )


def _active_stream_url(project_id: str, stream_id: str, kind: str) -> str | None:
    query = urlencode({"stream_id": stream_id})
    if kind == "generation":
        path = "generate/stream"
    elif kind == "modules":
        path = "generate/modules/stream"
    elif kind == "regenerate":
        path = "generate/regenerate/stream"
    elif kind.startswith("module:"):
        module_id = kind.removeprefix("module:")
        if not module_id or "/" in module_id or "\\" in module_id:
            return None
        path = f"generate/module/{module_id}/stream"
    else:
        # Reject/resume URLs may contain teacher feedback. They are deliberately
        # not reconstructed or exposed by discovery.
        return None
    return f"/api/projects/{project_id}/{path}?{query}"


@router.get("/{project_id}/generate/active-stream")
async def get_active_stream(
    project_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, object | None]:
    """Discover the latest replayable project stream without leaking its payload."""
    from db.models import SSEStream
    from sqlalchemy import select

    parsed_project_id = parse_project_id(project_id)
    rows = (
        await session.scalars(
            select(SSEStream)
            .where(
                SSEStream.project_id == parsed_project_id,
                SSEStream.status == "active",
            )
            .order_by(SSEStream.created_at.desc())
            .limit(20)
        )
    ).all()
    for stream in rows:
        stream_url = _active_stream_url(project_id, str(stream.id), stream.kind)
        if stream_url is not None:
            return {
                "stream_url": stream_url,
                "stream_id": str(stream.id),
                "kind": stream.kind,
                "last_event_id": stream.last_event_id,
                "created_at": stream.created_at,
            }
    return {"stream_url": None}


async def _instrument_sse(source):
    from services.telemetry import (
        record_sse_connection_closed,
        record_sse_connection_started,
    )

    record_sse_connection_started()
    outcome = "disconnected"
    try:
        async for event in source:
            if event.get("event") in {"done", "error", "waiting_approval"}:
                outcome = str(event["event"])
            yield event
    except Exception:
        outcome = "error"
        raise
    finally:
        record_sse_connection_closed(outcome)


def _last_event_id(request: Request) -> int:
    raw = request.headers.get("last-event-id", "0")
    try:
        return max(int(raw), 0)
    except (TypeError, ValueError):
        return 0


def _resume_capable_stream(
    source, request: Request, *, project_id: str, kind: str, stream_id: str | None
):
    if stream_id:
        try:
            uuid.UUID(stream_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail="Invalid SSE stream ID"
            ) from exc
        from services.sse_ledger import durable_sse_stream

        return _instrument_sse(
            durable_sse_stream(
                source,
                stream_id=stream_id,
                project_id=project_id,
                kind=kind,
                last_event_id=_last_event_id(request),
            )
        )
    return _instrument_sse(
        with_sse_metadata(source, last_event_id=_last_event_id(request))
    )


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

    # 更新状态；记录本次生成模式供 GET stream 读取（stream 无 body）
    project.status = "planning"
    snap = dict(project.dsl_snapshot or {})
    snap["_pending_action"] = body.action
    if body.modules:
        snap["_pending_modules"] = body.modules
    project.dsl_snapshot = snap

    logger.info("生成启动: project=%s | action=%s", project_id, body.action)

    stream_id = str(uuid.uuid4())
    return {
        "stream_url": f"/api/projects/{project_id}/generate/stream?stream_id={stream_id}"
    }


@router.get("/{project_id}/generate/stream")
async def generation_stream(
    project_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
    stream_id: str | None = None,
):
    """SSE 流式推送生成进度。"""
    from db.models import Project as ProjectModel

    # 获取项目信息
    project = await session.get(ProjectModel, parse_project_id(project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    input_content = ""
    constraints = {}
    action = "full"
    selected_modules: list[str] = []
    if project.dsl_snapshot:
        input_content = project.dsl_snapshot.get("input_content", project.title)
        constraints = project.dsl_snapshot.get("constraints", {})
        action = project.dsl_snapshot.get("_pending_action", "full")
        selected_modules = project.dsl_snapshot.get("_pending_modules", [])

    # Generation consumes the persisted parse result. Parsing belongs to the
    # material endpoint/worker boundary and must not block an SSE request.
    materials: list[dict] = []
    material_ids = (
        constraints.get("material_ids", []) if isinstance(constraints, dict) else []
    )
    if material_ids:
        from db.models import Material
        from sqlalchemy import select

        parsed_ids = []
        for material_id in material_ids:
            try:
                parsed_ids.append(uuid.UUID(str(material_id)))
            except ValueError:
                continue
        query = select(Material).where(Material.id.in_(parsed_ids))
        if project.owner_id:
            query = query.where(Material.owner_id == uuid.UUID(project.owner_id))
        rows = await session.scalars(query)
        by_id = {str(material.id): material for material in rows.all()}
        for mid in material_ids:
            record = by_id.get(str(mid))
            parsed = record.parsed_result if record is not None else None
            if parsed and parsed.get("raw_text"):
                materials.append(
                    {
                        "material_id": str(mid),
                        "content_text": parsed["raw_text"],
                        "topics": parsed.get("topics", []),
                    }
                )
            elif record is not None:
                logger.info("跳过未解析素材: material=%s", mid)
        logger.info("生成载入素材: project=%s | count=%d", project_id, len(materials))

    async def event_generator():
        async for sse_chunk in run_generation_stream(
            project_id=project_id,
            user_input=input_content,
            action=action,
            constraints=constraints,
            materials=materials,
            selected_modules=selected_modules,
            actor_id=str(current_user.id) if current_user is not None else None,
            actor_role=current_user.role if current_user is not None else None,
        ):
            # 检查客户端是否断开
            if await request.is_disconnected():
                break
            yield sse_chunk

    return EventSourceResponse(
        _resume_capable_stream(
            event_generator(),
            request,
            project_id=project_id,
            kind="generation",
            stream_id=stream_id,
        )
    )


@router.get("/{project_id}/generate/resume/stream")
async def generation_resume_stream(
    project_id: str,
    request: Request,
    decision: str = "approve",
    feedback: str = "",
    session: AsyncSession = Depends(get_session),
    stream_id: str | None = None,
):
    """从 HITL 中断点恢复生成流程的 SSE 流。

    Query:
        decision: approve | reject
        feedback: 拒绝时的修改意见
    """
    from db.models import Project as ProjectModel

    project = await session.get(ProjectModel, parse_project_id(project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

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

    return EventSourceResponse(
        _resume_capable_stream(
            event_generator(),
            request,
            project_id=project_id,
            kind="resume",
            stream_id=stream_id,
        )
    )


@router.post("/{project_id}/regenerate", status_code=202)
async def regenerate_frames(
    project_id: str,
    body: RegenerateRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """局部重生成指定帧范围。

    从 DB frames 表读取锁定帧、从 dsl_snapshot 读取已有规划/知识图谱，
    跳过 Planner+Knowledge，直接驱动 Coder→Quality→Reflection 循环。
    """
    from db.models import Project as ProjectModel

    project = await session.get(ProjectModel, parse_project_id(project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    scope = body.scope

    from services.regeneration import normalize_regeneration_scope

    try:
        scope = normalize_regeneration_scope(scope)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail="Invalid regeneration scope"
        ) from exc

    logger.info(
        "重生成: project=%s | scope=%s", project_id, scope.get("type", "unknown")
    )

    stream_id = str(uuid.uuid4())
    return {
        "stream_url": (
            f"/api/projects/{project_id}/generate/regenerate/stream?"
            + urlencode(
                {
                    "scope": json.dumps(scope, separators=(",", ":")),
                    "stream_id": stream_id,
                }
            )
        ),
    }


@router.get("/{project_id}/generate/regenerate/stream")
async def regenerate_stream(
    project_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
    scope_json: Annotated[str | None, Query(alias="scope", max_length=4000)] = None,
    stream_id: str | None = None,
):
    """局部重生成的 SSE 进度流（跳过 Planner+Knowledge，直接到 Coder）。"""
    from db.models import Project as ProjectModel

    project = await session.get(ProjectModel, parse_project_id(project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    from services.regeneration import normalize_regeneration_scope

    try:
        scope = normalize_regeneration_scope(
            json.loads(scope_json) if scope_json else {"type": "all_frames"}
        )
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=422, detail="Invalid regeneration scope"
        ) from exc

    async def event_generator():
        async for sse_chunk in run_regenerate_stream(
            project_id=project_id,
            scope=scope,
            actor_id=str(current_user.id) if current_user is not None else None,
            actor_role=current_user.role if current_user is not None else None,
        ):
            if await request.is_disconnected():
                break
            yield sse_chunk

    return EventSourceResponse(
        _resume_capable_stream(
            event_generator(),
            request,
            project_id=project_id,
            kind="regenerate",
            stream_id=stream_id,
        )
    )


@router.post("/{project_id}/generate/approve", status_code=200)
async def approve_plan(
    project_id: str,
    body: ApprovePlanRequest = ApprovePlanRequest(),
    session: AsyncSession = Depends(get_session),
) -> ApprovePlanResponse:
    """批准教学计划，清除 pending_approval 并继续生成流程。

    前端调用此端点后，应重新连接 SSE stream 继续接收后续进度。
    """
    from db.models import Project as ProjectModel

    project = await session.get(ProjectModel, parse_project_id(project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # 清除审批标记，更新状态（整体重赋值以触发 JSONB 变更检测）
    if project.dsl_snapshot:
        snap = dict(project.dsl_snapshot)
        snap.pop("pending_approval", None)
        # 反悔机制：如果用户调整了模块，覆盖此前选择
        if body.modules is not None:
            snap["_pending_modules"] = body.modules
        project.dsl_snapshot = snap
    project.status = "generating"

    logger.info("教学计划已批准: project=%s modules=%s", project_id, body.modules)

    stream_id = str(uuid.uuid4())
    return ApprovePlanResponse(
        stream_url=(
            f"/api/projects/{project_id}/generate/resume/stream?"
            + urlencode({"decision": "approve", "stream_id": stream_id})
        )
    )


@router.post("/{project_id}/generate/reject", status_code=200)
async def reject_plan(
    project_id: str,
    body: RejectPlanRequest,
    session: AsyncSession = Depends(get_session),
) -> ApprovePlanResponse:
    """拒绝教学计划，携带修改意见重新规划。

    将用户反馈写入 project DSL snapshot，前端可重新触发生成流程。
    """
    from db.models import Project as ProjectModel

    project = await session.get(ProjectModel, parse_project_id(project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # 记录拒绝反馈（整体重赋值以触发 JSONB 变更检测）
    if project.dsl_snapshot:
        snap = dict(project.dsl_snapshot)
        snap["approval_feedback"] = body.feedback
        snap.pop("pending_approval", None)
        project.dsl_snapshot = snap
    project.status = "draft"

    logger.info(
        "教学计划被拒绝: project=%s | feedback=%s", project_id, body.feedback[:100]
    )

    # 连接 resume 流注入拒绝决定，让图正常消费中断点后结束
    from urllib.parse import quote

    stream_id = str(uuid.uuid4())
    return ApprovePlanResponse(
        stream_url=(
            f"/api/projects/{project_id}/generate/resume/stream"
            f"?decision=reject&feedback={quote(body.feedback)}&stream_id={stream_id}"
        ),
    )


# ============================================================================
# 模块生成端点（Phase A）
# ============================================================================


@router.get("/{project_id}/generate/modules", response_model=ModuleListResponse)
async def list_available_modules(
    project_id: str,
    session: AsyncSession = Depends(get_session),
) -> ModuleListResponse:
    """获取可用于该项目生成的模块列表。

    从注册表中读取所有已注册的 ModuleGenerator，返回其元信息供前端渲染选择器。
    不依赖项目状态，模块列表纯内存读取。
    """
    modules = []
    for gen in list_generators():
        modules.append(
            ModuleInfo(
                module_id=gen.module_id,
                display_name=gen.display_name,
                description=gen.description,
                icon=gen.icon,
                category=gen.category,
                priority=gen.priority,
                estimated_seconds=30,  # 默认预估，各模块可覆写
            )
        )

    # 按优先级排序
    modules.sort(key=lambda m: m.priority)

    logger.info("可用模块列表: project=%s count=%d", project_id, len(modules))
    return ModuleListResponse(modules=modules)


@router.post(
    "/{project_id}/generate/modules/cost-estimate",
    response_model=ModuleCostEstimateResponse,
)
async def estimate_module_generation_cost(
    project_id: str,
    body: ModuleSelectRequest,
    session: AsyncSession = Depends(get_session),
) -> ModuleCostEstimateResponse:
    """Return a non-binding estimate derived only from priced historical traces."""
    from db.models import Project as ProjectModel

    project = await session.get(ProjectModel, parse_project_id(project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    unknown = [module_id for module_id in body.modules if get_generator(module_id) is None]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown module(s): {', '.join(unknown)}",
        )
    scheduled_modules = set(body.modules)
    if get_generator("frames") is not None:
        scheduled_modules.add("frames")
    return await _estimate_module_cost(session, project_id, len(scheduled_modules))


@router.post("/{project_id}/generate/modules", status_code=202)
async def start_module_generation(
    project_id: str,
    body: ModuleSelectRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """提交选中的模块，返回 SSE 流地址开始生成。

    验证所有选中的模块 ID 均已注册，存储选择到 project snapshot，
    返回模块生成流 URL。
    """
    from db.models import Project as ProjectModel

    project = await session.get(ProjectModel, parse_project_id(project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # 验证模块 ID
    unknown = [m for m in body.modules if get_generator(m) is None]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown module(s): {', '.join(unknown)}",
        )

    # 存储模块选择 + 标记
    snap = dict(project.dsl_snapshot or {})
    snap["_pending_modules"] = body.modules
    project.dsl_snapshot = snap
    project.status = "generating"

    logger.info("模块生成启动: project=%s modules=%s", project_id, body.modules)

    stream_id = str(uuid.uuid4())
    return {
        "stream_url": f"/api/projects/{project_id}/generate/modules/stream?stream_id={stream_id}",
        "modules": body.modules,
    }


@router.get("/{project_id}/generate/modules/stream")
async def module_generation_stream(
    project_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    stream_id: str | None = None,
):
    """SSE 流式推送多模块生成进度。

    从 DB 读取已审批的 teaching_plan + 选中的模块列表，
    通过 ModuleDispatcher 调度生成。
    """
    from agents.state import AgentState
    from db.models import Project as ProjectModel

    project = await session.get(ProjectModel, parse_project_id(project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    snap = project.dsl_snapshot or {}
    teaching_plan = snap.get("teaching_plan", {})
    knowledge_graph = snap.get("knowledge_graph", {})
    user_input = snap.get("input_content", snap.get("topic", ""))
    constraints = snap.get("constraints", {})
    selected_modules = snap.get("_pending_modules", ["frames"])

    # 构建 AgentState
    state: AgentState = {
        "user_input": user_input,
        "project_id": project_id,
        "teaching_plan": teaching_plan,
        "knowledge_graph": knowledge_graph,
        "constraints": constraints,
        "selected_modules": selected_modules,
        "status": "generating",
        "reflection_count": 0,
        "revision_history": [],
    }

    async def event_generator():
        async for sse_chunk in run_modules_stream(project_id, state, selected_modules):
            if await request.is_disconnected():
                break
            yield sse_chunk

    return EventSourceResponse(
        _resume_capable_stream(
            event_generator(),
            request,
            project_id=project_id,
            kind="modules",
            stream_id=stream_id,
        )
    )


# ============================================================================
# 单模块重新生成（Phase F）
# ============================================================================


@router.get("/{project_id}/generate/module/{module_id}/stream")
async def single_module_stream(
    project_id: str,
    module_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    stream_id: str | None = None,
):
    """SSE 流式推送单个模块的重新生成进度。"""
    from agents.state import AgentState
    from db.models import Project as ProjectModel

    project = await session.get(ProjectModel, parse_project_id(project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    gen = get_generator(module_id)
    if gen is None:
        raise HTTPException(status_code=400, detail=f"Unknown module: {module_id}")

    from services.project_persistence import load_canonical_project_dsl

    snap = await load_canonical_project_dsl(project, session) or {}
    state: AgentState = {
        "user_input": snap.get("input_content", snap.get("topic", "")),
        "project_id": project_id,
        "teaching_plan": snap.get("teaching_plan", {}),
        "knowledge_graph": snap.get("knowledge_graph", {}),
        "constraints": snap.get("constraints", {}),
        "selected_modules": [module_id],
        # A single-artifact retry must not silently regenerate Frames. Existing
        # artifacts satisfy declared dependencies (for example video -> frames)
        # without being written as new outputs.
        "ensure_frames": False,
        "module_context_outputs": snap.get("module_outputs", {}),
        "status": "generating",
        "reflection_count": 0,
        "revision_history": [],
    }

    async def event_generator():
        async for chunk in run_modules_stream(project_id, state, [module_id]):
            if await request.is_disconnected():
                break
            yield chunk

    return EventSourceResponse(
        _resume_capable_stream(
            event_generator(),
            request,
            project_id=project_id,
            kind=f"module:{module_id}",
            stream_id=stream_id,
        )
    )
