"""生成流程 API 路由。

POST   /api/projects/{id}/generate             启动生成
GET    /api/projects/{id}/generate/stream       SSE 进度流
POST   /api/projects/{id}/regenerate           局部重生成
GET    /api/projects/{id}/generate/modules     获取可用模块列表
POST   /api/projects/{id}/generate/modules     提交模块选择开始生成
GET    /api/projects/{id}/generate/modules/stream 模块生成 SSE 流
"""

from __future__ import annotations

import asyncio
import json
import logging
import statistics
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from db.database import get_session
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

from .auth import get_current_user, require_editor
from .deps import ensure_project_access, parse_project_id

logger = logging.getLogger(__name__)

UNSTARTED_STREAM_GRACE = timedelta(seconds=5)

router = APIRouter(
    prefix="/projects",
    tags=["generate"],
    dependencies=[Depends(require_editor)],
)


async def _request_credentials(session: AsyncSession, current_user, reference: dict | None = None):
    if current_user is None:
        return None, None
    from services.provider_credentials import (
        CredentialConfigurationError,
        CredentialReferenceUnavailableError,
        CredentialUnavailableError,
        resolve_credential_reference,
    )
    try:
        return await resolve_credential_reference(session, current_user.id, reference)
    except CredentialReferenceUnavailableError as exc:
        raise HTTPException(status_code=428, detail=str(exc)) from exc
    except CredentialUnavailableError as exc:
        # A transient KMS/unwrap outage is a service failure, not a missing
        # user precondition. Keep the distinction visible to clients so they
        # can retry without rotating an otherwise valid credential.
        raise HTTPException(status_code=503, detail="Credential service is temporarily unavailable") from exc
    except CredentialConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


async def _request_llm_limits(session: AsyncSession, current_user) -> tuple[int, float] | None:
    if current_user is None:
        return None
    from services.quota import resolve_user_llm_limits
    return await resolve_user_llm_limits(session, current_user.id)


async def _ensure_material_processing_consent(
    session: AsyncSession, current_user, constraints: dict | None
) -> None:
    """Require a current explicit consent before sending material to a model."""
    if current_user is None or not isinstance(constraints, dict):
        return
    if not constraints.get("allow_material_model_processing", False):
        return
    from api.auth import CURRENT_POLICY_VERSION
    from db.models import UserConsent

    accepted = await session.scalar(
        select(UserConsent).where(
            UserConsent.user_id == current_user.id,
            UserConsent.policy == "model_processing",
            UserConsent.policy_version == CURRENT_POLICY_VERSION,
        )
    )
    if accepted is None:
        raise HTTPException(
            status_code=428,
            detail="Explicit model-processing consent is required before using uploaded materials",
        )


async def _latest_generation_credential_ref(
    session: AsyncSession, current_user
) -> dict[str, object] | None:
    """Capture only the credential id/version for a queued workflow."""
    if current_user is None:
        return None
    from services.provider_credentials import selected_provider_credential

    row = await selected_provider_credential(session, current_user.id, "generation")
    if row is None:
        return None
    return {"id": str(row.id), "version": row.version}


async def _stream_credential_ref(
    session: AsyncSession, current_user, project, stream_id: str | None
) -> dict[str, object] | None:
    """Resolve the immutable credential reference attached to this stream."""
    if current_user is not None and stream_id:
        from db.models import UsageLedger

        rows = list(
            (
                await session.scalars(
                    select(UsageLedger).where(
                        UsageLedger.user_id == current_user.id,
                        UsageLedger.resource == "generation",
                    )
                )
            ).all()
        )
        for row in rows:
            details = row.details if isinstance(row.details, dict) else {}
            if details.get("stream_id") == stream_id:
                value = details.get("credential_ref")
                if isinstance(value, dict):
                    return value
    if project is not None and isinstance(project.dsl_snapshot, dict):
        value = project.dsl_snapshot.get("_credential_ref")
        if isinstance(value, dict):
            return value
    return None


async def _ensure_generation_stream_admission(
    session: AsyncSession,
    current_user,
    *,
    project_id: str,
    stream_id: str | None,
    action: str,
) -> None:
    """Prevent direct SSE URLs from bypassing user generation quotas.

    POST admission endpoints persist the stream id in the quota ledger. A
    reconnect finds that row and is free; a direct stream URL receives one
    normal, idempotent admission so it cannot evade limits. Deployed clients
    must provide a stream id, while legacy anonymous development remains
    compatible.
    """
    if current_user is None:
        return
    from config import get_settings
    if not stream_id:
        if get_settings().environment in {"staging", "production"}:
            raise HTTPException(status_code=422, detail="A stream id is required")
        return

    from db.models import Project as ProjectModel
    from db.models import UsageLedger
    from services.quota import (
        QuotaExceededError,
        acquire_quota_lock,
        quota_limit,
        reserve_quota,
    )
    credential_ref = await _latest_generation_credential_ref(session, current_user)
    if credential_ref is None:
        raise HTTPException(status_code=428, detail="A generation provider credential is required")
    rows = list((await session.scalars(select(UsageLedger).where(
        UsageLedger.user_id == current_user.id,
        UsageLedger.resource == "generation",
    ))).all())
    if any(
        isinstance(row.details, dict) and row.details.get("stream_id") == stream_id
        for row in rows
    ):
        return

    try:
        await acquire_quota_lock(session, user_id=current_user.id, resource="generation")
        from sqlalchemy import func
        active_count = int(await session.scalar(select(func.count(ProjectModel.id)).where(
            ProjectModel.owner_id == str(current_user.id),
            ProjectModel.status.in_(("planning", "generating", "reviewing")),
        )) or 0)
        concurrent_limit = await quota_limit(
            session, user_id=current_user.id, resource="generation_concurrent"
        )
        if active_count >= concurrent_limit:
            raise HTTPException(
                status_code=409,
                detail={"error": {"code": "CONCURRENCY_LIMIT", "message": "Another generation is already active",
                                   "details": {"limit": concurrent_limit}}},
            )
        await reserve_quota(
            session,
            user_id=current_user.id,
            resource="generation",
            idempotency_key=f"stream:{stream_id}",
            count_toward_limit=credential_ref is None,
            details={
                "project_id": project_id,
                "action": action,
                "stream_id": stream_id,
                **(
                    {"credential_ref": credential_ref}
                    if isinstance(credential_ref, dict)
                    else {}
                ),
            },
        )
    except QuotaExceededError as exc:
        raise HTTPException(
            status_code=429,
            detail={"error": {"code": "QUOTA_EXCEEDED", "message": "Generation quota exceeded",
                               "details": {"resource": exc.resource, "period": exc.period, "limit": exc.limit}}},
        ) from exc


async def _credentialed_events(source, credentials, llm_limits=None):
    from services.provider_credentials import credential_scope
    from services.quota import user_llm_limits_scope
    try:
        with credential_scope(*credentials):
            if llm_limits is None:
                async for event in source:
                    yield event
            else:
                with user_llm_limits_scope(llm_limits):
                    async for event in source:
                        yield event
    finally:
        # CredentialContext contains the only plaintext provider references
        # used by a request. Drop the local tuple as soon as streaming ends or
        # is cancelled; it must never outlive the SSE request accidentally.
        credentials = (None, None)
        source = None


async def _estimate_module_cost(
    session: AsyncSession, project_id: str, requested_count: int
) -> ModuleCostEstimateResponse:
    """Estimate from recent successful, non-zero module-node traces."""
    from sqlalchemy import select

    from config import get_settings
    from db.models import WorkflowNodeRun, WorkflowRun

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


async def _finalize_stream_quota(
    session: AsyncSession,
    current_user,
    *,
    project_id: str,
    stream_id: str | None,
    status: str,
    quota_ref: dict | None = None,
) -> None:
    """Settle successful streams or release streams that failed before start."""
    if current_user is None:
        return
    from db.models import UsageLedger
    from services.quota import release_quota, settle_quota

    key = None
    if isinstance(quota_ref, dict):
        candidate = quota_ref.get("idempotency_key")
        if isinstance(candidate, str) and candidate:
            key = candidate
    if key is None and stream_id:
        rows = list((await session.scalars(select(UsageLedger).where(
            UsageLedger.user_id == current_user.id,
            UsageLedger.resource == "generation",
        ))).all())
        for row in rows:
            details = row.details if isinstance(row.details, dict) else {}
            if details.get("stream_id") == stream_id and details.get("project_id") in {None, project_id}:
                key = row.idempotency_key
                break
    if not key:
        return
    if status == "error":
        await release_quota(
            session, user_id=current_user.id, resource="generation", idempotency_key=key
        )
    elif status in {"done", "cancelled"}:
        await settle_quota(
            session, user_id=current_user.id, resource="generation", idempotency_key=key
        )


@router.get("/{project_id}/generate/active-stream")
async def get_active_stream(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: Annotated[object | None, Depends(get_current_user)] = None,
) -> dict[str, object | None]:
    """Discover the latest replayable project stream without leaking its payload."""
    from sqlalchemy import select

    from db.models import Project, SSEStream

    parsed_project_id = parse_project_id(project_id)
    project = await session.get(Project, parsed_project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    ensure_project_access(project, current_user)
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


async def _instrument_sse(source, on_terminal=None):
    from services.telemetry import (
        record_sse_connection_closed,
        record_sse_connection_started,
    )

    record_sse_connection_started()
    outcome = "disconnected"
    finalized = False
    async def finalize(status: str) -> None:
        nonlocal finalized
        if finalized or on_terminal is None:
            return
        finalized = True
        try:
            await on_terminal(status)
        except Exception:
            # Quota finalization is retried idempotently on the next replay;
            # it must not turn a successful user stream into a 500.
            logger.exception("generation quota finalization failed")

    try:
        async for event in source:
            if event.get("event") in {"done", "error", "waiting_approval"}:
                outcome = str(event["event"])
            if event.get("event") in {"done", "error"}:
                await finalize(str(event["event"]))
            yield event
    except asyncio.CancelledError:
        await finalize("cancelled")
        outcome = "cancelled"
        raise
    except Exception:
        await finalize("error")
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
    source, request: Request, *, project_id: str, kind: str, stream_id: str | None,
    on_terminal=None,
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
            ),
            on_terminal=on_terminal,
        )
    return _instrument_sse(
        with_sse_metadata(source, last_event_id=_last_event_id(request)),
        on_terminal=on_terminal,
    )


async def _recover_or_resume_generation(
    session: AsyncSession, current_user, project, *, project_id: str
) -> str | None:
    """Resume a live run or retire a reservation whose SSE never started."""
    if current_user is None or not isinstance(project.dsl_snapshot, dict):
        return None
    quota_ref = project.dsl_snapshot.get("_quota_ref")
    if not isinstance(quota_ref, dict):
        return None
    raw_stream_id = quota_ref.get("stream_id")
    quota_key = quota_ref.get("idempotency_key")
    if not isinstance(raw_stream_id, str) or not raw_stream_id:
        return None
    try:
        parsed_stream_id = uuid.UUID(raw_stream_id)
    except ValueError:
        return None

    from db.models import SSEStream
    from services.quota import release_quota

    stream = await session.get(SSEStream, parsed_stream_id)
    now = datetime.now(UTC)
    created_at = stream.created_at if stream is not None else None
    if created_at is not None and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    unstarted = (
        stream is None
        or (
            stream.status == "active"
            and stream.producer_id is None
            and stream.last_event_id == 0
            and created_at is not None
            and now - created_at >= UNSTARTED_STREAM_GRACE
        )
    )
    if not unstarted:
        if stream is not None and stream.status == "active":
            return f"/api/projects/{project_id}/generate/stream?stream_id={raw_stream_id}"
        return None

    if isinstance(quota_key, str) and quota_key:
        await release_quota(
            session,
            user_id=current_user.id,
            resource="generation",
            idempotency_key=quota_key,
        )
    if stream is not None:
        stream.status = "completed"
        stream.completed_at = now
        stream.producer_id = None
        stream.lease_expires_at = None
    snapshot = dict(project.dsl_snapshot)
    snapshot.pop("_quota_ref", None)
    project.dsl_snapshot = snapshot
    if project.status in {"planning", "generating", "reviewing"}:
        project.status = "draft"
    logger.warning(
        "已回收未建立连接的生成流: project=%s | stream=%s", project_id, raw_stream_id
    )
    return None


@router.post("/{project_id}/generate", status_code=202)
async def start_generation(
    project_id: str,
    body: GenerateRequest,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=1, max_length=200)
    ] = None,
) -> dict:
    """启动生成流程。返回 SSE 流地址。"""
    from db.models import Project as ProjectModel

    # 验证项目存在
    project = await session.get(ProjectModel, parse_project_id(project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    ensure_project_access(project, current_user)
    await _ensure_material_processing_consent(session, current_user, body.constraints)

    resumable_stream_url = await _recover_or_resume_generation(
        session, current_user, project, project_id=project_id
    )
    if resumable_stream_url is not None:
        return {"stream_url": resumable_stream_url}

    stream_id = str(uuid.uuid4())
    normalized_idempotency_key = idempotency_key.strip() if idempotency_key else None
    if idempotency_key is not None and not normalized_idempotency_key:
        raise HTTPException(status_code=422, detail="Idempotency-Key must not be blank")
    quota_key = normalized_idempotency_key or f"stream:{stream_id}"
    if current_user is not None and normalized_idempotency_key:
        # Return the original stream for a client retry instead of re-running
        # admission checks or consuming another unit.  The stream keeps the
        # credential version captured by the first request.
        from sqlalchemy import select

        from db.models import UsageLedger
        existing = await session.scalar(select(UsageLedger).where(
            UsageLedger.user_id == current_user.id,
            UsageLedger.resource == "generation",
            UsageLedger.idempotency_key == normalized_idempotency_key,
        ))
        if existing is not None:
            details = existing.details if isinstance(existing.details, dict) else {}
            if details.get("project_id") not in {None, project_id}:
                raise HTTPException(status_code=409, detail="Idempotency key already used for another project")
            if details.get("action") not in {None, body.action}:
                raise HTTPException(status_code=409, detail="Idempotency key already used for another generation action")
            prior_stream = details.get("stream_id")
            if isinstance(prior_stream, str) and prior_stream:
                return {"stream_url": f"/api/projects/{project_id}/generate/stream?stream_id={prior_stream}"}
    generation_credentials = await _request_credentials(session, current_user)
    if current_user is not None:
        from services.quota import (
            QuotaExceededError,
            acquire_quota_lock,
            quota_limit,
            reserve_quota,
        )
        await acquire_quota_lock(session, user_id=current_user.id, resource="generation")
        from sqlalchemy import func
        active_count = int(await session.scalar(
            select(func.count(ProjectModel.id))
            .where(
                ProjectModel.owner_id == str(current_user.id),
                ProjectModel.id != parse_project_id(project_id),
                ProjectModel.status.in_(("planning", "generating", "reviewing")),
            )
        ) or 0)
        concurrent_limit = await quota_limit(
            session, user_id=current_user.id, resource="generation_concurrent"
        )
        if active_count >= concurrent_limit:
            raise HTTPException(
                status_code=409,
                detail={"error": {"code": "CONCURRENCY_LIMIT", "message": "Another generation is already active",
                        "details": {"limit": concurrent_limit}}},
            )
        # Check concurrency before consuming the daily/monthly admission
        # ledger.  A rejected concurrent request must not burn a quota unit.
        try:
            await reserve_quota(
                session, user_id=current_user.id, resource="generation",
                idempotency_key=quota_key,
                count_toward_limit=generation_credentials[0] is None,
                details={
                    "project_id": project_id,
                    "action": body.action,
                    "stream_id": stream_id,
                    **(
                        {
                            "credential_ref": {
                                "id": str(generation_credentials[0].credential_id),
                                "version": generation_credentials[0].version,
                            }
                        }
                        if generation_credentials[0] is not None
                        else {}
                    ),
                },
            )
        except QuotaExceededError as exc:
            raise HTTPException(
                status_code=429,
                detail={"error": {"code": "QUOTA_EXCEEDED", "message": "Generation quota exceeded",
                        "details": {"resource": exc.resource, "period": exc.period, "limit": exc.limit}}},
            ) from exc

    # 更新状态；记录本次生成模式供 GET stream 读取（stream 无 body）
    project.status = "planning"
    snap = dict(project.dsl_snapshot or {})
    snap["_pending_action"] = body.action
    if body.modules:
        snap["_pending_modules"] = body.modules
    if body.constraints is not None:
        snap["constraints"] = dict(body.constraints)
    if generation_credentials[0] is not None:
        snap["_credential_ref"] = {
            "id": str(generation_credentials[0].credential_id),
            "version": generation_credentials[0].version,
        }
    if current_user is not None:
        snap["_quota_ref"] = {
            "resource": "generation", "idempotency_key": quota_key,
            "stream_id": stream_id,
        }
    project.dsl_snapshot = snap

    # The replay handle must exist before its URL is exposed.  Previously it
    # was created only when the response body started iterating, leaving a
    # planning project and reserved quota behind if the browser never opened
    # the SSE request.
    from services.sse_ledger import register_sse_stream

    await register_sse_stream(
        session, stream_id=stream_id, project_id=project_id, kind="generation"
    )

    logger.info("生成启动: project=%s | action=%s", project_id, body.action)

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

    ensure_project_access(project, current_user)
    await _ensure_generation_stream_admission(
        session, current_user, project_id=project_id, stream_id=stream_id, action="full"
    )

    input_content = ""
    constraints = {}
    action = "full"
    selected_modules: list[str] = []
    if project.dsl_snapshot:
        input_content = project.dsl_snapshot.get("input_content", project.title)
        constraints = project.dsl_snapshot.get("constraints", {})
        action = project.dsl_snapshot.get("_pending_action", "full")
        selected_modules = project.dsl_snapshot.get("_pending_modules", [])

    await _ensure_material_processing_consent(session, current_user, constraints)

    # Generation consumes the persisted parse result. Parsing belongs to the
    # material endpoint/worker boundary and must not block an SSE request.
    materials: list[dict] = []
    material_ids = (
        constraints.get("material_ids", []) if isinstance(constraints, dict) else []
    )
    if material_ids and not constraints.get("allow_material_model_processing", False):
        logger.info(
            "素材未发送给模型：缺少用户的显式处理授权 | project=%s", project_id
        )
        material_ids = []
    if material_ids:
        from sqlalchemy import select

        from db.models import Material

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

    credential_ref = await _stream_credential_ref(session, current_user, project, stream_id)
    credentials = await _request_credentials(session, current_user, credential_ref)
    llm_limits = await _request_llm_limits(session, current_user)

    async def event_generator():
        source = run_generation_stream(
            project_id=project_id,
            user_input=input_content,
            action=action,
            constraints=constraints,
            materials=materials,
            selected_modules=selected_modules,
            actor_id=str(current_user.id) if current_user is not None else None,
            actor_role=current_user.role if current_user is not None else None,
        )
        async for sse_chunk in _credentialed_events(source, credentials, llm_limits):
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
            on_terminal=lambda terminal_status: _finalize_stream_quota(
                session, current_user, project_id=project_id, stream_id=stream_id,
                status=terminal_status,
            ),
        ),
        ping=15,
    )


@router.get("/{project_id}/generate/resume/stream")
async def generation_resume_stream(
    project_id: str,
    request: Request,
    decision: str = "approve",
    feedback: str = "",
    session: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
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

    ensure_project_access(project, current_user)

    resume_value = (
        {
            "action": "reject",
            # Reject feedback is persisted by the POST endpoint.  Reading it
            # from the project snapshot keeps the SSE URL free of user text,
            # which also prevents it from appearing in browser history or
            # HTTP/OTel request attributes.
            "feedback": feedback
            or (
                project.dsl_snapshot.get("approval_feedback", "")
                if isinstance(project.dsl_snapshot, dict)
                else ""
            ),
        }
        if decision == "reject"
        else {"action": "approve"}
    )
    credential_ref = await _stream_credential_ref(session, current_user, project, stream_id)
    credentials = await _request_credentials(session, current_user, credential_ref)
    llm_limits = await _request_llm_limits(session, current_user)
    quota_ref = project.dsl_snapshot.get("_quota_ref") if project.dsl_snapshot else None

    async def event_generator():
        source = resume_generation_stream(project_id, resume_value)
        async for sse_chunk in _credentialed_events(source, credentials, llm_limits):
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
            on_terminal=lambda terminal_status: _finalize_stream_quota(
                session, current_user, project_id=project_id, stream_id=stream_id,
                status=terminal_status, quota_ref=quota_ref,
            ),
        ),
        ping=15,
    )


@router.post("/{project_id}/regenerate", status_code=202)
async def regenerate_frames(
    project_id: str,
    body: RegenerateRequest,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=1, max_length=200)
    ] = None,
) -> dict:
    """局部重生成指定帧范围。

    从 DB frames 表读取锁定帧、从 dsl_snapshot 读取已有规划/知识图谱，
    跳过 Planner+Knowledge，直接驱动 Coder→Quality→Reflection 循环。
    """
    from db.models import Project as ProjectModel

    project = await session.get(ProjectModel, parse_project_id(project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    ensure_project_access(project, current_user)

    scope = body.scope

    from services.regeneration import normalize_regeneration_scope

    try:
        scope = normalize_regeneration_scope(scope)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail="Invalid regeneration scope"
        ) from exc

    normalized_idempotency_key = idempotency_key.strip() if idempotency_key else None
    if idempotency_key is not None and not normalized_idempotency_key:
        raise HTTPException(status_code=422, detail="Idempotency-Key must not be blank")
    if current_user is not None and normalized_idempotency_key:
        # A retry must return the original stream instead of enqueueing another
        # regeneration.  The persisted scope is authoritative for the key.
        from db.models import UsageLedger

        existing = await session.scalar(select(UsageLedger).where(
            UsageLedger.user_id == current_user.id,
            UsageLedger.resource == "generation",
            UsageLedger.idempotency_key == normalized_idempotency_key,
        ))
        if existing is not None:
            details = existing.details if isinstance(existing.details, dict) else {}
            if details.get("project_id") not in {None, project_id}:
                raise HTTPException(status_code=409, detail="Idempotency key already used for another project")
            if details.get("action") not in {None, "regenerate"}:
                raise HTTPException(status_code=409, detail="Idempotency key already used for another generation action")
            prior_stream = details.get("stream_id")
            prior_scope = details.get("scope") if isinstance(details.get("scope"), dict) else scope
            if isinstance(prior_stream, str) and prior_stream:
                return {
                    "stream_url": (
                        f"/api/projects/{project_id}/generate/regenerate/stream?"
                        + urlencode({
                            "scope": json.dumps(prior_scope, separators=(",", ":")),
                            "stream_id": prior_stream,
                        })
                    )
                }

    stream_id = str(uuid.uuid4())
    credential_ref = await _latest_generation_credential_ref(session, current_user)
    if current_user is not None and credential_ref is None:
        raise HTTPException(status_code=428, detail="A generation provider credential is required")
    if current_user is not None:
        from sqlalchemy import func

        from services.quota import (
            QuotaExceededError,
            acquire_quota_lock,
            quota_limit,
            reserve_quota,
        )
        try:
            await acquire_quota_lock(session, user_id=current_user.id, resource="generation")
            active_count = int(await session.scalar(select(func.count(ProjectModel.id)).where(
                ProjectModel.owner_id == str(current_user.id),
                ProjectModel.status.in_(("planning", "generating", "reviewing")),
            )) or 0)
            if active_count >= await quota_limit(
                session, user_id=current_user.id, resource="generation_concurrent"
            ):
                raise HTTPException(
                    status_code=409,
                    detail={"error": {"code": "CONCURRENCY_LIMIT", "message": "Another generation is already active"}},
                )
            await reserve_quota(
                session, user_id=current_user.id, resource="generation",
                idempotency_key=normalized_idempotency_key or f"regenerate:{project_id}:{stream_id}",
                count_toward_limit=credential_ref is None,
                details={
                    "project_id": project_id,
                    "action": "regenerate",
                    "scope": scope,
                    "stream_id": stream_id,
                    **({"credential_ref": credential_ref} if credential_ref else {}),
                },
            )
        except QuotaExceededError as exc:
            raise HTTPException(
                status_code=429,
                detail={"error": {"code": "QUOTA_EXCEEDED", "message": "Generation quota exceeded",
                        "details": {"resource": exc.resource, "period": exc.period, "limit": exc.limit}}},
            ) from exc

    # Mark the project while the scoped stream is active so the per-user
    # concurrency gate also covers regenerate requests.
    project.status = "generating"

    logger.info(
        "重生成: project=%s | scope=%s", project_id, scope.get("type", "unknown")
    )

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

    ensure_project_access(project, current_user)
    await _ensure_generation_stream_admission(
        session, current_user, project_id=project_id, stream_id=stream_id, action="regenerate"
    )

    from services.regeneration import normalize_regeneration_scope

    try:
        scope = normalize_regeneration_scope(
            json.loads(scope_json) if scope_json else {"type": "all_frames"}
        )
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=422, detail="Invalid regeneration scope"
        ) from exc

    credential_ref = await _stream_credential_ref(session, current_user, project, stream_id)
    credentials = await _request_credentials(session, current_user, credential_ref)
    llm_limits = await _request_llm_limits(session, current_user)

    async def event_generator():
        source = run_regenerate_stream(
            project_id=project_id,
            scope=scope,
            actor_id=str(current_user.id) if current_user is not None else None,
            actor_role=current_user.role if current_user is not None else None,
        )
        async for sse_chunk in _credentialed_events(source, credentials, llm_limits):
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
            on_terminal=lambda terminal_status: _finalize_stream_quota(
                session, current_user, project_id=project_id, stream_id=stream_id,
                status=terminal_status,
            ),
        ),
        ping=15,
    )


@router.post("/{project_id}/generate/approve", status_code=200)
async def approve_plan(
    project_id: str,
    body: ApprovePlanRequest = ApprovePlanRequest(),
    session: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
) -> ApprovePlanResponse:
    """批准教学计划，清除 pending_approval 并继续生成流程。

    前端调用此端点后，应重新连接 SSE stream 继续接收后续进度。
    """
    from db.models import Project as ProjectModel

    project = await session.get(ProjectModel, parse_project_id(project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    ensure_project_access(project, current_user)

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
    current_user=Depends(get_current_user),
) -> ApprovePlanResponse:
    """拒绝教学计划，携带修改意见重新规划。

    将用户反馈写入 project DSL snapshot，前端可重新触发生成流程。
    """
    from db.models import Project as ProjectModel

    project = await session.get(ProjectModel, parse_project_id(project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    ensure_project_access(project, current_user)

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

    # 连接 resume 流注入拒绝决定，让图正常消费中断点后结束。反馈正文
    # 已写入项目快照，不拼入 URL，避免泄露到历史记录和请求 Trace。
    stream_id = str(uuid.uuid4())
    return ApprovePlanResponse(
        stream_url=(
            f"/api/projects/{project_id}/generate/resume/stream"
            f"?decision=reject&stream_id={stream_id}"
        ),
    )


# ============================================================================
# 模块生成端点（Phase A）
# ============================================================================


@router.get("/{project_id}/generate/modules", response_model=ModuleListResponse)
async def list_available_modules(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
) -> ModuleListResponse:
    """获取可用于该项目生成的模块列表。

    从注册表中读取所有已注册的 ModuleGenerator，返回其元信息供前端渲染选择器。
    不依赖项目状态，模块列表纯内存读取。
    """
    from db.models import Project as ProjectModel

    # ``_new`` is the client-side placeholder used before a project is
    # persisted. Module metadata is global, so it must still be available in
    # that state instead of falling through to the frontend's reduced fallback.
    project = (
        None
        if project_id == "_new"
        else await session.get(ProjectModel, parse_project_id(project_id))
    )
    # Module metadata is not tenant data and historically remains available
    # while a project is being created. If a project exists, still enforce its
    # ownership; the protected router performs the same check for HTTP calls.
    if project is not None:
        ensure_project_access(project, current_user)

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
    current_user=Depends(get_current_user),
) -> ModuleCostEstimateResponse:
    """Return a non-binding estimate derived only from priced historical traces."""
    from db.models import Project as ProjectModel

    project = await session.get(ProjectModel, parse_project_id(project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    ensure_project_access(project, current_user)
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
    current_user=Depends(get_current_user),
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=1, max_length=200)
    ] = None,
) -> dict:
    """提交选中的模块，返回 SSE 流地址开始生成。

    验证所有选中的模块 ID 均已注册，存储选择到 project snapshot，
    返回模块生成流 URL。
    """
    from db.models import Project as ProjectModel

    project = await session.get(ProjectModel, parse_project_id(project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    ensure_project_access(project, current_user)

    # 验证模块 ID
    unknown = [m for m in body.modules if get_generator(m) is None]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown module(s): {', '.join(unknown)}",
        )

    normalized_idempotency_key = idempotency_key.strip() if idempotency_key else None
    if idempotency_key is not None and not normalized_idempotency_key:
        raise HTTPException(status_code=422, detail="Idempotency-Key must not be blank")
    if current_user is not None and normalized_idempotency_key:
        from db.models import UsageLedger

        existing = await session.scalar(select(UsageLedger).where(
            UsageLedger.user_id == current_user.id,
            UsageLedger.resource == "generation",
            UsageLedger.idempotency_key == normalized_idempotency_key,
        ))
        if existing is not None:
            details = existing.details if isinstance(existing.details, dict) else {}
            if details.get("project_id") not in {None, project_id}:
                raise HTTPException(status_code=409, detail="Idempotency key already used for another project")
            if details.get("action") not in {None, "modules"}:
                raise HTTPException(status_code=409, detail="Idempotency key already used for another generation action")
            prior_stream = details.get("stream_id")
            if isinstance(prior_stream, str) and prior_stream:
                return {
                    "stream_url": f"/api/projects/{project_id}/generate/modules/stream?stream_id={prior_stream}",
                    "modules": details.get("modules", body.modules),
                }

    stream_id = str(uuid.uuid4())
    credential_ref = await _latest_generation_credential_ref(session, current_user)
    if current_user is not None and credential_ref is None:
        raise HTTPException(status_code=428, detail="A generation provider credential is required")
    if current_user is not None:
        from sqlalchemy import func

        from services.quota import (
            QuotaExceededError,
            acquire_quota_lock,
            quota_limit,
            reserve_quota,
        )
        try:
            await acquire_quota_lock(session, user_id=current_user.id, resource="generation")
            active_count = int(await session.scalar(
                select(func.count(ProjectModel.id)).where(
                    ProjectModel.owner_id == str(current_user.id),
                    ProjectModel.status.in_(("planning", "generating", "reviewing")),
                )
            ) or 0)
            if active_count >= await quota_limit(session, user_id=current_user.id, resource="generation_concurrent"):
                raise HTTPException(
                    status_code=409,
                    detail={"error": {"code": "CONCURRENCY_LIMIT", "message": "Another generation is already active"}},
                )
            await reserve_quota(
                session, user_id=current_user.id, resource="generation",
                idempotency_key=normalized_idempotency_key or f"modules:{project_id}:{stream_id}",
                count_toward_limit=credential_ref is None,
                details={
                    "project_id": project_id,
                    "action": "modules",
                    "module_count": len(body.modules),
                    "modules": body.modules,
                    "stream_id": stream_id,
                    **({"credential_ref": credential_ref} if credential_ref else {}),
                },
            )
        except QuotaExceededError as exc:
            raise HTTPException(
                status_code=429,
                detail={"error": {"code": "QUOTA_EXCEEDED", "message": "Generation quota exceeded",
                        "details": {"resource": exc.resource, "period": exc.period, "limit": exc.limit}}},
            ) from exc

    # 存储模块选择 + 标记
    snap = dict(project.dsl_snapshot or {})
    snap["_pending_modules"] = body.modules
    if credential_ref:
        snap["_credential_ref"] = credential_ref
    if current_user is not None:
        snap["_quota_ref"] = {
            "resource": "generation",
            "idempotency_key": normalized_idempotency_key or f"modules:{project_id}:{stream_id}",
            "stream_id": stream_id,
        }
    project.dsl_snapshot = snap
    project.status = "generating"

    logger.info("模块生成启动: project=%s modules=%s", project_id, body.modules)

    return {
        "stream_url": f"/api/projects/{project_id}/generate/modules/stream?stream_id={stream_id}",
        "modules": body.modules,
    }


@router.get("/{project_id}/generate/modules/stream")
async def module_generation_stream(
    project_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
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

    ensure_project_access(project, current_user)
    await _ensure_generation_stream_admission(
        session, current_user, project_id=project_id, stream_id=stream_id, action="modules"
    )

    snap = project.dsl_snapshot or {}
    teaching_plan = snap.get("teaching_plan", {})
    knowledge_graph = snap.get("knowledge_graph", {})
    user_input = snap.get("input_content", snap.get("topic", ""))
    constraints = snap.get("constraints", {})
    requested_modules = snap.get("_pending_modules", ["frames"])
    if not isinstance(requested_modules, list):
        requested_modules = ["frames"]
    persisted_outputs = snap.get("module_outputs")
    if not isinstance(persisted_outputs, dict):
        persisted_outputs = {}
    # A reconnect must continue the batch from its durable checkpoints instead
    # of regenerating modules that already completed before the SSE dropped.
    selected_modules = [
        module_id for module_id in requested_modules
        if isinstance(module_id, str) and module_id not in persisted_outputs
    ]

    # 构建 AgentState
    state: AgentState = {
        "user_input": user_input,
        "project_id": project_id,
        "teaching_plan": teaching_plan,
        "knowledge_graph": knowledge_graph,
        "constraints": constraints,
        "selected_modules": selected_modules,
        "module_context_outputs": persisted_outputs,
        "ensure_frames": not bool(persisted_outputs),
        "status": "generating",
        "reflection_count": 0,
        "revision_history": [],
    }
    credential_ref = await _stream_credential_ref(session, current_user, project, stream_id)
    credentials = await _request_credentials(session, current_user, credential_ref)
    llm_limits = await _request_llm_limits(session, current_user)

    async def event_generator():
        source = run_modules_stream(project_id, state, selected_modules)
        async for sse_chunk in _credentialed_events(source, credentials, llm_limits):
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
            on_terminal=lambda terminal_status: _finalize_stream_quota(
                session, current_user, project_id=project_id, stream_id=stream_id,
                status=terminal_status,
            ),
        ),
        ping=15,
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
    current_user=Depends(get_current_user),
    stream_id: str | None = None,
):
    """SSE 流式推送单个模块的重新生成进度。"""
    from agents.state import AgentState
    from db.models import Project as ProjectModel

    project = await session.get(ProjectModel, parse_project_id(project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    ensure_project_access(project, current_user)
    gen = get_generator(module_id)
    if gen is None:
        raise HTTPException(status_code=400, detail=f"Unknown module: {module_id}")
    await _ensure_generation_stream_admission(
        session, current_user, project_id=project_id, stream_id=stream_id, action=f"module:{module_id}"
    )

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
    credential_ref = await _stream_credential_ref(session, current_user, project, stream_id)
    credentials = await _request_credentials(session, current_user, credential_ref)
    llm_limits = await _request_llm_limits(session, current_user)

    async def event_generator():
        source = run_modules_stream(project_id, state, [module_id])
        async for chunk in _credentialed_events(source, credentials, llm_limits):
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
            on_terminal=lambda terminal_status: _finalize_stream_quota(
                session, current_user, project_id=project_id, stream_id=stream_id,
                status=terminal_status,
            ),
        ),
        ping=15,
    )
