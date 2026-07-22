"""生成流程服务。

负责：
- 调用 LangGraph Agent 编排
- 通过 SSE 将中间状态推送给前端
- 处理 Human-in-the-Loop 审批
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncGenerator

from agents.state import AgentState

logger = logging.getLogger(__name__)


async def run_generation_stream(
    project_id: str,
    user_input: str,
    *,
    action: str = "full",
    constraints: dict[str, Any] | None = None,
    materials: list[dict[str, Any]] | None = None,
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
    approval_mode = action == "plan_only"
    initial_state: AgentState = {
        "user_input": user_input,
        "project_id": project_id,
        "materials": materials or [],
        "constraints": constraints or {},
        "approval_mode": approval_mode,
        "status": "draft",
        "reflection_count": 0,
        "revision_history": [],
    }

    config = _thread_config(project_id)

    try:
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
    """从 HITL 中断点恢复生成流程（批准/拒绝）。

    使用同一 thread_id 通过 Command(resume=...) 注入用户决定，从断点继续，
    不重跑 Planner。

    Args:
        project_id: 项目 ID（= thread_id）
        resume_value: {"action": "approve"} 或 {"action": "reject", "feedback": ...}
    """
    from langgraph.types import Command

    graph = await _get_graph()
    config = _thread_config(project_id)

    try:
        async for chunk in _drive_graph(
            graph, Command(resume=resume_value), config, project_id
        ):
            yield chunk
    except Exception:
        logger.exception("恢复生成流程失败")
        yield _sse_event("error", {
            "phase": "error",
            "message": "恢复生成流程内部错误，请稍后重试",
            "error_code": "RESUME_FAILED",
        })


async def _drive_graph(
    graph,
    graph_input,
    config: dict[str, Any],
    project_id: str,
) -> AsyncGenerator[str, None]:
    """驱动图执行、映射阶段事件、处理 interrupt 与最终持久化。

    graph_input 可为初始 state（首次）或 Command(resume=...)（恢复）。
    """
    async for event in graph.astream_events(graph_input, config=config, version="v2"):
        event_type = event.get("event", "")

        if event_type == "on_chain_start":
            chain_name = event.get("name", "")
            if chain_name in ("planner", "knowledge", "coder", "quality", "reflection"):
                yield _sse_event("progress", {
                    "phase": chain_name,
                    "message": f"正在执行 {chain_name}...",
                    "pct": _phase_pct(chain_name),
                })

        elif event_type == "on_chain_end":
            chain_name = event.get("name", "")
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

    # 图执行到断点或结束 —— 检查是否处于 HITL 中断态
    final_state = await graph.aget_state(config)
    interrupt_payload = _extract_interrupt(final_state)
    if interrupt_payload is not None:
        teaching_plan = interrupt_payload.get("teaching_plan", {})
        yield _sse_event("waiting_approval", {
            "phase": "waiting_approval",
            "message": "教学计划已生成，请确认后继续",
            "pct": 28,
            "teaching_plan": teaching_plan,
        })
        return

    # 未中断 → 正常收尾（可能因拒绝而无 DSL）
    async for chunk in _finalize_done(final_state, project_id):
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


async def _finalize_done(final_state, project_id: str) -> AsyncGenerator[str, None]:
    """流程结束：持久化生成产物并发送 done 事件。"""
    try:
        if final_state and final_state.values:
            dsl = final_state.values.get("dsl", {})
            quality_report = final_state.values.get("quality_report", {})
            teaching_plan = final_state.values.get("teaching_plan", {})

            # 拒绝导致无 DSL 时不持久化，直接 done
            if dsl:
                try:
                    from db.database import async_session_factory
                    from db.models import Project as ProjectModel
                    from api.versions import save_version
                    from services.project_persistence import (
                        merge_dsl_snapshot,
                        persist_frames_to_table,
                    )
                    from api.deps import parse_project_id

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
                            await save_version(project_id, dsl, "Agent 生成", db_session)
                            await db_session.commit()
                except Exception as perr:
                    logger.warning("生成产物持久化失败: %s", perr)

            yield _sse_event("done", {
                "phase": "done",
                "pct": 100,
                "dsl": dsl,
                "quality_report": quality_report,
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


async def run_generation_sync(
    project_id: str,
    user_input: str,
    *,
    constraints: dict[str, Any] | None = None,
    materials: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """同步执行生成流程（非流式），返回最终状态。

    用于内部调用或测试。
    """
    from agents.graph import get_graph

    graph = get_graph()
    initial_state: AgentState = {
        "user_input": user_input,
        "project_id": project_id,
        "materials": materials or [],
        "constraints": constraints or {},
        "approval_mode": False,
        "status": "draft",
        "reflection_count": 0,
        "revision_history": [],
    }

    result = await graph.ainvoke(initial_state, {
        "configurable": {"thread_id": project_id},
    })

    return result


# ── Helpers ─────────────────────────────────────────────────


def _sse_event(event: str, data: dict[str, Any]) -> str:
    """构建 SSE 格式字符串。"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _phase_pct(phase: str) -> int:
    """各阶段的进度百分比。"""
    mapping = {
        "planner": 10,
        "knowledge": 25,
        "coder": 50,
        "quality": 80,
        "reflection": 85,
    }
    return mapping.get(phase, 50)
