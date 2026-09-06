"""生成流程服务。

负责：
- 调用 LangGraph Agent 编排
- 通过 SSE 将中间状态推送给前端
- 处理 Human-in-the-Loop 审批
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncGenerator, AsyncIterable
from typing import Any

from agents.state import AgentState

logger = logging.getLogger(__name__)


async def run_generation_stream(
    project_id: str,
    user_input: str,
    *,
    action: str = "full",
    constraints: dict[str, Any] | None = None,
    materials: list[dict[str, Any]] | None = None,
    selected_modules: list[str] | None = None,
    actor_id: str | None = None,
    actor_role: str | None = None,
) -> AsyncGenerator[str, None]:
    """执行生成流程并以 SSE 格式流式推送进度。

    Args:
        project_id: 项目 ID
        user_input: 用户输入主题
        action: 生成模式 (full / plan_only / frames_only)
        constraints: 教师约束
        materials: 上传材料解析结果
    """
    graph = await _get_graph()
    # plan_only 模式：启用 HITL 审批（Planner 后 interrupt 等待确认）
    approval_mode = action in ("plan_only", "modules")
    initial_state: AgentState = {
        "workflow_entry": "planner",
        "user_input": user_input,
        "project_id": project_id,
        "materials": materials or [],
        "constraints": constraints or {},
        "enable_retrieval": True,
        "enable_tools": True,
        "approval_mode": approval_mode,
        "selected_modules": selected_modules or [],
        "status": "draft",
        "reflection_count": 0,
        "replan_count": 0,
        "revision_history": [],
    }

    config = _thread_config(project_id)

    try:
        with _workflow_llm_budget():
            async for chunk in _drive_graph(graph, initial_state, config, project_id):
                yield chunk
    except Exception:
        logger.exception("生成流程失败")
        yield _sse_event("error", {
            "phase": "error",
            "message": "生成流程内部错误，请稍后重试",
            "error_code": "GENERATION_FAILED",
        })


async def resume_generation_stream(
    project_id: str,
    resume_value: dict[str, Any],
) -> AsyncGenerator[str, None]:
    """Resume the persisted HITL interrupt inside the canonical LangGraph."""
    from langgraph.types import Command

    try:
        graph = await _get_graph()
        with _workflow_llm_budget():
            async for chunk in _drive_graph(
                graph,
                Command(resume=resume_value),
                _thread_config(project_id),
                project_id,
            ):
                yield chunk
    except Exception:
        logger.exception("恢复生成流程失败")
        yield _sse_event("error", {
            "phase": "error",
            "message": "恢复生成失败，请确认审批状态后重试",
            "error_code": "RESUME_FAILED",
        })


async def run_regenerate_stream(
    project_id: str,
    *,
    scope: dict[str, Any] | None = None,
    actor_id: str | None = None,
    actor_role: str | None = None,
) -> AsyncGenerator[str, None]:
    """Enter the canonical graph at Coder for a scoped regeneration."""
    from api.deps import parse_project_id
    from db.database import async_session_factory
    from db.models import Frame as FrameModel
    from db.models import Project as ProjectModel
    from sqlalchemy import select

    from services.regeneration import (
        normalize_regeneration_scope,
        resolve_target_frame_ids,
    )

    try:
        scope = normalize_regeneration_scope(scope)
    except ValueError:
        yield _sse_event("error", {
            "phase": "error",
            "message": "重生成范围无效",
            "error_code": "INVALID_REGENERATE_SCOPE",
        })
        return
    try:
        async with async_session_factory() as db_session:
            project = await db_session.get(ProjectModel, parse_project_id(project_id))
            if project is None or not project.dsl_snapshot:
                yield _sse_event("error", {
                    "phase": "error",
                    "message": "项目无已有 DSL，请先生成",
                    "error_code": "NO_DSL",
                })
                return
            snap = project.dsl_snapshot
            lock_res = await db_session.execute(
                select(FrameModel.frame_id).where(
                    FrameModel.project_id == parse_project_id(project_id),
                    FrameModel.is_locked.is_(True),
                )
            )
            locked_frame_ids = [row[0] for row in lock_res.fetchall()]
    except Exception:
        logger.exception("读取 regenerate 上下文失败")
        yield _sse_event("error", {
            "phase": "error",
            "message": "读取项目数据失败，请稍后重试",
            "error_code": "REGENERATE_CONTEXT_FAILED",
        })
        return

    existing_dsl = {key: value for key, value in snap.items() if key in {
        "frames", "parameters", "teaching_strategy", "topic", "audience",
        "difficulty", "project_id", "assets", "export_targets",
    }}
    target_frame_ids = resolve_target_frame_ids(existing_dsl.get("frames", []), scope)
    if not target_frame_ids:
        yield _sse_event("error", {
            "phase": "error",
            "message": "重生成范围未匹配任何现有帧",
            "error_code": "INVALID_REGENERATE_SCOPE",
        })
        return
    all_frame_ids = {
        str(frame.get("frame_id"))
        for frame in existing_dsl.get("frames", [])
        if isinstance(frame, dict) and frame.get("frame_id")
    }
    protected_frame_ids = set(locked_frame_ids) | (all_frame_ids - target_frame_ids)
    state: AgentState = {
        "workflow_entry": "coder",
        "regenerate_scope": scope,
        "user_input": snap.get("topic", snap.get("input_content", "")),
        "project_id": project_id,
        "actor_id": actor_id,
        "actor_role": actor_role,
        "teaching_plan": snap.get("teaching_plan", {}),
        "knowledge_graph": snap.get("knowledge_graph", {}),
        "dsl": existing_dsl,
        "constraints": snap.get("constraints", {}),
        "materials": [],
        "approval_mode": False,
        # Reflection uses this same protection set, so it cannot rewrite frames
        # outside the requested range after Coder's deterministic merge.
        "locked_frame_ids": sorted(protected_frame_ids),
        "status": "generating",
        "reflection_count": 0,
        "replan_count": 0,
        "revision_history": [],
    }
    graph = await _get_graph()
    run_id = f"{project_id}:regenerate:{uuid.uuid4().hex}"
    try:
        with _workflow_llm_budget():
            async for chunk in _drive_graph(
                graph, state, _thread_config(run_id), project_id,
                change_summary=f"局部重生成 ({scope.get('type', 'from_frame')})",
            ):
                yield chunk
    except Exception:
        logger.exception("Regenerate 失败")
        yield _sse_event("error", {
            "phase": "error",
            "message": "重生成失败，请稍后重试",
            "error_code": "REGENERATE_FAILED",
        })


async def _save_interim_teaching_plan(project_id: str, teaching_plan: dict) -> None:
    """HITL 中断时：将 teaching_plan 持久化到 DB，避免切 Tab 后丢失。"""
    try:
        from api.deps import parse_project_id
        from db.database import async_session_factory
        from db.models import Project as ProjectModel

        async with async_session_factory() as db_session:
            project = await db_session.get(ProjectModel, parse_project_id(project_id))
            if project is not None:
                snap = dict(project.dsl_snapshot or {})
                snap["teaching_plan"] = teaching_plan
                project.dsl_snapshot = snap
                project.current_version_id = None
                await db_session.commit()
    except Exception as exc:
        logger.warning("teaching_plan 暂存失败: %s", exc)


async def _drive_graph(
    graph,
    graph_input,
    config: dict[str, Any],
    project_id: str,
    *,
    change_summary: str = "Agent 生成",
) -> AsyncGenerator[str, None]:
    """Run one invocation inside a durable workflow trace."""
    from services.workflow_trace import workflow_trace_scope

    entrypoint = (
        str(graph_input.get("workflow_entry", "planner"))
        if isinstance(graph_input, dict)
        else "resume"
    )
    thread_id = str(config.get("configurable", {}).get("thread_id", project_id))
    async with workflow_trace_scope(
        project_id=project_id,
        thread_id=thread_id,
        entrypoint=entrypoint,
    ):
        async for chunk in _drive_graph_events(
            graph,
            graph_input,
            config,
            project_id,
            change_summary=change_summary,
        ):
            yield chunk


async def _drive_graph_events(
    graph,
    graph_input,
    config: dict[str, Any],
    project_id: str,
    *,
    change_summary: str = "Agent 生成",
) -> AsyncGenerator[str, None]:
    """驱动图执行、映射阶段事件、处理 interrupt 与最终持久化。

    graph_input 可为初始 state（首次）或 Command(resume=...)（恢复）。
    """
    # 立即推送连接事件，避免前端在 LLM 调用期间静默超时
    yield _sse_event("progress", {
        "phase": "connecting",
        "message": "正在连接 Agent 编排引擎...",
        "pct": 0,
    })

    async for event in graph.astream_events(graph_input, config=config, version="v2"):
        event_type = event.get("event", "")
        chain_name = event.get("name", "")
        traceable = chain_name in (
            "planner", "knowledge", "coder", "quality", "reflection", "modules"
        )
        from services.workflow_trace import observe_graph_trace_event

        await observe_graph_trace_event(event)

        if event_type == "on_chain_start":
            if traceable:
                yield _sse_event("progress", {
                    "phase": chain_name,
                    "message": f"正在执行 {chain_name}...",
                    "pct": _phase_pct(chain_name),
                })

        elif event_type == "on_custom_event" and chain_name == "eduflow_module_event":
            custom = event.get("data", {})
            outbound_event = custom.get("event") if isinstance(custom, dict) else None
            payload = custom.get("payload") if isinstance(custom, dict) else None
            if outbound_event in {
                "progress",
                "module_start",
                "module_done",
                "module_error",
            } and isinstance(payload, dict):
                yield _sse_event(outbound_event, payload)

        elif event_type == "on_chain_end":
            output = event.get("data", {}).get("output", {})

            if chain_name == "planner" and isinstance(output, dict):
                yield _sse_event("progress", {
                    "phase": "planning",
                    "message": "教学计划已生成",
                    "pct": 30,
                    "teaching_plan": output.get("teaching_plan", {}),
                })

            elif chain_name == "knowledge" and isinstance(output, dict):
                kg = output.get("knowledge_graph", {})
                terms = output.get("key_terms", [])
                yield _sse_event("progress", {
                    "phase": "knowledge",
                    "message": f"知识图谱构建完成 ({len(kg.get('concepts', []))} 概念, {len(terms)} 术语)",
                    "pct": 40,
                    "knowledge_graph": kg,
                })

            elif chain_name == "quality" and isinstance(output, dict):
                yield _sse_event("progress", {
                    "phase": "validating",
                    "message": "质量校验完成",
                    "pct": 90,
                    "quality_report": output.get("quality_report", {}),
                })

            elif chain_name == "coder" and isinstance(output, dict):
                dsl = output.get("dsl", {})
                frame_count = len(dsl.get("frames", []))
                yield _sse_event("progress", {
                    "phase": "generating",
                    "message": f"已完成 {frame_count} 帧生成",
                    "pct": 70,
                    "frame_count": frame_count,
                })

            elif chain_name == "modules" and isinstance(output, dict):
                module_outputs = output.get("module_outputs", {})
                module_errors = output.get("module_errors", {})
                yield _sse_event("progress", {
                    "phase": "modules",
                    "message": (
                        f"模块生成完成：{len(module_outputs)} 成功 / "
                        f"{len(module_errors)} 失败"
                    ),
                    "pct": 95,
                    "module_outputs": module_outputs,
                    "module_errors": module_errors or None,
                })

    # 图执行到断点或结束 —— 检查是否处于 HITL 中断态
    final_state = await graph.aget_state(config)
    interrupt_payload = _extract_interrupt(final_state)
    if interrupt_payload is not None:
        from services.workflow_trace import set_workflow_trace_status

        set_workflow_trace_status("waiting_approval")
        teaching_plan = interrupt_payload.get("teaching_plan", {})

        # 中断时持久化 teaching_plan 到 DB，避免切 Tab 后"计划也没保留"
        await _save_interim_teaching_plan(project_id, teaching_plan)

        yield _sse_event("waiting_approval", {
            "phase": "waiting_approval",
            "message": "教学计划已生成，请确认后继续",
            "pct": 28,
            "teaching_plan": teaching_plan,
        })
        return

    # 未中断 → 正常收尾（可能因拒绝而无 DSL）
    async for chunk in _finalize_done(
        final_state, project_id, change_summary=change_summary
    ):
        yield chunk


def _extract_interrupt(final_state) -> dict[str, Any] | None:
    """从 graph state 中提取 HITL interrupt 载荷；无中断返回 None。"""
    if not final_state:
        return None
    # LangGraph 将待处理中断挂在 state.tasks[*].interrupts 上
    tasks = getattr(final_state, "tasks", None)
    if not isinstance(tasks, (list, tuple)):
        return None
    for task in tasks:
        interrupts = getattr(task, "interrupts", None)
        if not isinstance(interrupts, (list, tuple)):
            continue
        for intr in interrupts:
            value = getattr(intr, "value", None)
            if isinstance(value, dict):
                return value
    return None


async def _finalize_done(
    final_state, project_id: str, *, change_summary: str = "Agent 生成"
) -> AsyncGenerator[str, None]:
    """流程结束：持久化生成产物并发送 done 事件。"""
    try:
        if final_state and final_state.values:
            values = final_state.values
            dsl = values.get("dsl", {})
            quality_report = values.get("quality_report", {})
            teaching_plan = values.get("teaching_plan", {})
            module_outputs = values.get("module_outputs", {})
            module_errors = values.get("module_errors", {})

            if module_outputs or module_errors:
                await _persist_module_result(
                    project_id,
                    teaching_plan=teaching_plan,
                    knowledge_graph=values.get("knowledge_graph", {}),
                    selected_modules=values.get("selected_modules", []),
                    module_dependencies=values.get("module_dependencies", {}),
                    module_outputs=module_outputs,
                    module_errors=module_errors,
                    change_summary=change_summary,
                )
            # 拒绝导致无 DSL 时不持久化，直接 done。模块流程由上面的
            # 专用分支落库，避免 frames 产物再写一次通用版本。
            elif dsl:
                await _persist_dsl_result(
                    project_id, dsl,
                    quality_report=quality_report,
                    teaching_plan=teaching_plan,
                    change_summary=change_summary,
                )

            yield _sse_event("done", {
                "phase": "done",
                "pct": 100,
                "dsl": dsl,
                "quality_report": quality_report,
                "module_outputs": module_outputs,
                "module_errors": module_errors,
            })
        else:
            yield _sse_event("done", {"phase": "done", "pct": 100})
    except Exception as state_err:
        logger.warning("获取最终状态失败: %s", state_err)
        yield _sse_event("done", {"phase": "done", "pct": 100})


async def _get_graph():
    """获取编排图（优先 async 工厂以接入 Postgres checkpointer）。"""
    from agents.graph import get_graph_async
    return await get_graph_async()


def _thread_config(project_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": project_id}}


def _workflow_llm_budget():
    from config import get_settings

    from services.telemetry import llm_budget_scope

    settings = get_settings()
    return llm_budget_scope(
        settings.llm_request_max_tokens,
        settings.llm_request_max_cost_usd,
    )


async def run_generation_sync(
    project_id: str,
    user_input: str,
    *,
    constraints: dict[str, Any] | None = None,
    materials: list[dict[str, Any]] | None = None,
    thread_id: str | None = None,
) -> dict[str, Any]:
    """同步执行生成流程（非流式），返回最终状态。

    用于内部调用或测试。
    """
    result, _usage = await run_generation_sync_with_usage(
        project_id,
        user_input,
        constraints=constraints,
        materials=materials,
        thread_id=thread_id,
    )
    return result


async def run_generation_sync_with_usage(
    project_id: str,
    user_input: str,
    *,
    constraints: dict[str, Any] | None = None,
    materials: list[dict[str, Any]] | None = None,
    thread_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, int | float]]:
    """Run the production graph and return per-workflow Token/cost accounting."""
    from agents.graph import get_graph

    graph = get_graph()
    initial_state: AgentState = {
        "workflow_entry": "planner",
        "user_input": user_input,
        "project_id": project_id,
        "materials": materials or [],
        "constraints": constraints or {},
        "approval_mode": False,
        "status": "draft",
        "reflection_count": 0,
        "replan_count": 0,
        "revision_history": [],
    }

    with _workflow_llm_budget() as budget:
        result = await graph.ainvoke(initial_state, {
            "configurable": {"thread_id": thread_id or project_id},
        })

    return result, {
        "input": budget.input_tokens,
        "output": budget.output_tokens,
        "total": budget.used_tokens,
        "cost_usd": round(budget.used_cost_usd, 8),
    }


async def run_modules_stream(
    project_id: str,
    state: AgentState,
    selected_modules: list[str],
) -> AsyncGenerator[str, None]:
    """Enter the canonical graph at Modules for initial or retry batches."""
    graph_state: AgentState = {
        **state,
        "workflow_entry": "modules",
        "selected_modules": selected_modules,
        "approval_mode": False,
    }
    graph = await _get_graph()
    run_id = f"{project_id}:modules:{uuid.uuid4().hex}"
    try:
        with _workflow_llm_budget():
            async for chunk in _drive_graph(
                graph,
                graph_state,
                _thread_config(run_id),
                project_id,
                change_summary="模块产物生成",
            ):
                yield chunk
    except Exception:
        logger.exception("模块 Graph 执行失败")
        yield _sse_event("error", {
            "phase": "error",
            "message": "模块生成失败，请稍后重试",
            "error_code": "MODULE_GENERATION_FAILED",
        })

# ── Helpers ─────────────────────────────────────────────────


async def _persist_dsl_result(
    project_id: str,
    dsl: dict[str, Any],
    *,
    quality_report: dict[str, Any] | None,
    teaching_plan: dict[str, Any],
    change_summary: str,
) -> None:
    """持久化生成产物：merge dsl_snapshot + status=done + frames 表 + 版本记录。

    统一 full 生成 / resume / regenerate 三条链路的落库逻辑（此前为三份同构代码）。
    保持既有权衡：失败仅降级为 warning 日志，不中断 SSE 流。
    """
    try:
        from api.deps import parse_project_id
        from api.versions import save_version
        from db.database import async_session_factory
        from db.models import Project as ProjectModel

        from services.project_persistence import (
            merge_dsl_snapshot,
            persist_frames_to_table,
        )

        async with async_session_factory() as db_session:
            project = await db_session.get(ProjectModel, parse_project_id(project_id))
            if project is not None:
                project.dsl_snapshot = merge_dsl_snapshot(
                    project.dsl_snapshot,
                    dsl,
                    quality_report=quality_report,
                    teaching_plan=teaching_plan,
                )
                project.status = "done"
                await persist_frames_to_table(
                    project_id, dsl.get("frames", []), db_session
                )
                await save_version(
                    project_id,
                    project.dsl_snapshot,
                    change_summary,
                    db_session,
                )
                await db_session.commit()
    except Exception as perr:
        logger.warning("生成产物持久化失败: %s", perr)


async def _persist_module_result(
    project_id: str,
    *,
    teaching_plan: dict[str, Any],
    knowledge_graph: dict[str, Any],
    selected_modules: list[str],
    module_dependencies: dict[str, list[str]],
    module_outputs: dict[str, Any],
    module_errors: dict[str, str],
    change_summary: str,
) -> None:
    """Persist one module batch once, including its dependency provenance."""
    try:
        from api.deps import parse_project_id
        from api.versions import save_version
        from db.database import async_session_factory
        from db.models import Project as ProjectModel

        from services.project_persistence import (
            merge_dsl_snapshot,
            persist_frames_to_table,
        )

        async with async_session_factory() as db_session:
            project = await db_session.get(ProjectModel, parse_project_id(project_id))
            if project is None:
                return

            frames_output = module_outputs.get("frames")
            frames_dsl = (
                frames_output
                if isinstance(frames_output, dict) and frames_output.get("frames")
                else None
            )
            project.dsl_snapshot = merge_dsl_snapshot(
                project.dsl_snapshot,
                frames_dsl,
                teaching_plan=teaching_plan,
                knowledge_graph=knowledge_graph,
                selected_modules=selected_modules,
                module_dependencies=module_dependencies,
                module_outputs=module_outputs,
                module_errors=module_errors,
            )
            if frames_dsl is not None:
                await persist_frames_to_table(
                    project_id, frames_dsl.get("frames", []), db_session
                )
            if module_outputs:
                await save_version(
                    project_id,
                    project.dsl_snapshot,
                    change_summary,
                    db_session,
                )
                project.status = "done"
            elif module_errors:
                project.status = "failed"
            await db_session.commit()
    except Exception as perr:
        logger.warning("模块产物持久化失败: %s", perr)


def _sse_event(event: str, data: dict[str, Any]) -> dict[str, str]:
    """构建 SSE 事件（返回 dict，由 sse-starlette EventSourceResponse 编码）。

    sse-starlette 3.x 对 string 会二次包 data: → 前端收不到。
    返 dict({"event": ..., "data": json.dumps(...)}) 由 sse-starlette 正确格式化。
    """
    return {"event": event, "data": json.dumps(data, ensure_ascii=False)}


async def with_sse_metadata(
    source: AsyncIterable[dict[str, str]], *, last_event_id: int = 0
) -> AsyncGenerator[dict[str, str], None]:
    """Add deterministic event IDs and skip events already seen by a client.

    This establishes the wire protocol. Durable event storage is intentionally
    separate; replay currently re-drives the checkpointed graph and filters the
    deterministic prefix.
    """
    sequence = 0
    terminal_sent = False
    async for event in source:
        sequence += 1
        event_name = str(event.get("event") or "progress")
        if sequence <= max(last_event_id, 0):
            continue
        if terminal_sent:
            continue
        try:
            payload = json.loads(event.get("data", "{}"))
        except (TypeError, json.JSONDecodeError):
            payload = {"message": "Malformed server event"}
        if not isinstance(payload, dict):
            payload = {"value": payload}
        payload["schema_version"] = "1.0"
        payload["event_id"] = sequence
        enriched = {
            **event,
            "id": str(sequence),
            "event": event_name,
            "data": json.dumps(payload, ensure_ascii=False),
        }
        yield enriched
        if event_name in {"done", "error", "waiting_approval"}:
            terminal_sent = True


def _phase_pct(phase: str) -> int:
    """各阶段的进度百分比。"""
    mapping = {
        "planner": 10,
        "knowledge": 25,
        "coder": 50,
        "quality": 80,
        "reflection": 85,
        "modules": 55,
    }
    return mapping.get(phase, 50)
