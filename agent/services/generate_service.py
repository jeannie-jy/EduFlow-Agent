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

    不再依赖 LangGraph Command + astream_events（1.2.9 里 resume 语义不稳定），
    改为直接显式调用 knowledge_node → coder_node → quality_node → reflection。
    与 run_regenerate_stream 同模式。

    Args:
        project_id: 项目 ID
        resume_value: {"action": "approve"} 或 {"action": "reject", "feedback": ...}
    """
    if resume_value.get("action") == "reject":
        # Phase F: 拒绝+反馈 → 重跑 Planner 并注入反馈
        feedback = resume_value.get("feedback", "")
        yield _sse_event("progress", {
            "phase": "planning",
            "message": "正在根据反馈重新制定教学计划...",
            "pct": 5,
        })

        try:
            from db.database import async_session_factory
            from db.models import Project as ProjectModel
            from api.deps import parse_project_id

            async with async_session_factory() as db_session:
                project = await db_session.get(ProjectModel, parse_project_id(project_id))
                if project is None or not project.dsl_snapshot:
                    yield _sse_event("error", {"phase": "error", "message": "项目数据缺失", "error_code": "NO_PROJECT"})
                    return
                snap = project.dsl_snapshot
        except Exception as exc:
            logger.exception("读取项目数据失败")
            yield _sse_event("error", {"phase": "error", "message": f"读取失败: {exc}", "error_code": "RESUME_CONTEXT_FAILED"})
            return

        user_input = snap.get("input_content", snap.get("topic", ""))
        old_plan = snap.get("teaching_plan", {})
        replan_count = snap.get("_replan_count", 0)
        max_replan = 3

        if replan_count >= max_replan:
            yield _sse_event("done", {"phase": "done", "pct": 100, "message": f"已达最大重规划次数 ({max_replan}次)，请重新开始"})
            return

        # 上下文清理：只保留原始主题 + 最新大纲 + 汇总反馈
        from agents.nodes import planner_node
        from agents.state import AgentState

        replan_state: AgentState = {
            "user_input": user_input,
            "project_id": project_id,
            "teaching_plan": old_plan,
            "constraints": snap.get("constraints", {}),
            "materials": [],
            "approval_mode": True,
            "user_feedback": {"type": "plan_reject", "content": feedback},
            "selected_modules": snap.get("_pending_modules", []),
            "status": "draft",
            "reflection_count": 0,
            "revision_history": [],
        }

        # 保存 replan 计数
        try:
            async with async_session_factory() as db_session:
                p = await db_session.get(ProjectModel, parse_project_id(project_id))
                if p and p.dsl_snapshot:
                    s = dict(p.dsl_snapshot)
                    s["_replan_count"] = replan_count + 1
                    s["_replan_feedback"] = (s.get("_replan_feedback", "") + f"\n[第{replan_count+1}次]: {feedback}").strip()
                    p.dsl_snapshot = s
                    await db_session.commit()
        except Exception:
            pass

        logger.info("Replan 第 %d/%d 次 | project=%s", replan_count + 1, max_replan, project_id)

        try:
            result = await planner_node(replan_state)
            new_plan = result.get("teaching_plan", old_plan)

            # 持久化新计划
            try:
                async with async_session_factory() as db_session:
                    p = await db_session.get(ProjectModel, parse_project_id(project_id))
                    if p and p.dsl_snapshot:
                        s = dict(p.dsl_snapshot)
                        s["teaching_plan"] = new_plan
                        p.dsl_snapshot = s
                        await db_session.commit()
            except Exception:
                pass

            yield _sse_event("waiting_approval", {
                "phase": "waiting_approval",
                "message": "教学计划已根据反馈重新生成，请确认",
                "pct": 28,
                "teaching_plan": new_plan,
            })
        except Exception as exc:
            logger.exception("Replan 失败")
            yield _sse_event("error", {"phase": "error", "message": f"重新规划失败: {exc}", "error_code": "REPLAN_FAILED"})
        return

    # ── 批准：从 DB 读 teaching_plan，通过 dispatch_modules 调度生成 ──
    from agents.state import AgentState

    # 1. 从 DB 读取上下文
    try:
        from db.database import async_session_factory
        from db.models import Project as ProjectModel
        from api.deps import parse_project_id

        async with async_session_factory() as db_session:
            project = await db_session.get(ProjectModel, parse_project_id(project_id))
            if project is None or not project.dsl_snapshot:
                yield _sse_event("error", {
                    "phase": "error",
                    "message": "项目数据缺失，请重新生成",
                    "error_code": "NO_PROJECT",
                })
                return
            snap = project.dsl_snapshot
    except Exception as exc:
        logger.exception("读取项目数据失败")
        yield _sse_event("error", {
            "phase": "error",
            "message": f"读取项目数据失败: {exc}",
            "error_code": "RESUME_CONTEXT_FAILED",
        })
        return

    teaching_plan = snap.get("teaching_plan", {})
    user_input = snap.get("input_content", snap.get("topic", ""))
    selected_modules = snap.get("_pending_modules", [])

    state: AgentState = {
        "user_input": user_input,
        "project_id": project_id,
        "teaching_plan": teaching_plan,
        "knowledge_graph": snap.get("knowledge_graph", {}),
        "constraints": snap.get("constraints", {}),
        "materials": [],
        "approval_mode": False,
        "selected_modules": selected_modules,
        "status": "generating",
        "reflection_count": 0,
        "revision_history": [],
    }

    logger.info("Resume(approve): 调度 %d 个模块 | project=%s", len(selected_modules), project_id)

    try:
        if selected_modules:
            # Phase E: 使用 dispatch_modules 调度用户选中的模块
            from services.module_dispatcher import dispatch_modules
            async for chunk in dispatch_modules(project_id, state, selected_modules):
                yield chunk
        else:
            # 向后兼容：无 selected_modules 时走旧流程
            from agents.nodes import knowledge_node, coder_node, quality_node, reflection_node
            from config import get_settings

            settings = get_settings()

            k_result = await knowledge_node(state)
            state.update(k_result)

            c_result = await coder_node(state)
            state.update(c_result)

            max_cycles = settings.max_reflection_cycles
            for cycle in range(max_cycles + 1):
                q_result = await quality_node(state)
                state.update(q_result)
                quality_report = state.get("quality_report", {})
                if (quality_report.get("overall_score", 1.0) < settings.quality_score_threshold
                        or quality_report.get("is_blocking", False)) and cycle < max_cycles:
                    r_result = await reflection_node(state)
                    state.update(r_result)
                    state["reflection_count"] = cycle + 1
                else:
                    break

            dsl = state.get("dsl", {})
            try:
                from db.database import async_session_factory
                from db.models import Project as ProjectModel
                from api.versions import save_version
                from services.project_persistence import merge_dsl_snapshot, persist_frames_to_table
                async with async_session_factory() as db_session:
                    project = await db_session.get(ProjectModel, parse_project_id(project_id))
                    if project is not None:
                        project.dsl_snapshot = merge_dsl_snapshot(
                            project.dsl_snapshot, dsl,
                            quality_report=state.get("quality_report"),
                            teaching_plan=teaching_plan,
                        )
                        project.status = "done"
                        await persist_frames_to_table(project_id, dsl.get("frames", []), db_session)
                        await save_version(project_id, dsl, "Agent 生成", db_session)
                        await db_session.commit()
            except Exception as perr:
                logger.warning("Resume 持久化失败: %s", perr)

            yield _sse_event("done", {
                "phase": "done", "pct": 100,
                "dsl": dsl, "quality_report": state.get("quality_report"),
            })

    except Exception as exc:
        logger.exception("Resume 失败")
        yield _sse_event("error", {
            "phase": "error",
            "message": f"恢复生成失败: {exc}",
            "error_code": "RESUME_FAILED",
        })


async def run_regenerate_stream(
    project_id: str,
    *,
    scope: dict[str, Any] | None = None,
) -> AsyncGenerator[str, None]:
    """局部重生成：读已有 DSL，显式驱动 Coder→Quality→Reflection 循环。

    不跑完整 LangGraph graph（其入口为 Planner，不可跳过），而是直接
    调用 coder_node→quality_node→reflection_node 纯函数，手动发 SSE。

    锁定帧（is_locked=True in DB）不会被 Reflection 修改。
    """
    from agents.nodes import coder_node, quality_node, reflection_node
    from agents.state import AgentState
    from config import get_settings

    settings = get_settings()
    scope = scope or {"type": "from_frame"}

    # 1. 从 DB 读已有状态
    try:
        from db.database import async_session_factory
        from db.models import Project as ProjectModel, Frame as FrameModel
        from api.deps import parse_project_id
        from sqlalchemy import select

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
            # 读取锁定帧
            locked_query = select(FrameModel.frame_id).where(
                FrameModel.project_id == parse_project_id(project_id),
                FrameModel.is_locked == True,
            )
            lock_res = await db_session.execute(locked_query)
            locked_frame_ids = [row[0] for row in lock_res.fetchall()]
    except Exception as exc:
        logger.exception("读取 regenerate 上下文失败")
        yield _sse_event("error", {
            "phase": "error",
            "message": f"读取项目数据失败: {exc}",
            "error_code": "REGENERATE_CONTEXT_FAILED",
        })
        return

    teaching_plan = snap.get("teaching_plan", {})
    knowledge_graph = snap.get("knowledge_graph", {})
    existing_dsl = {k: v for k, v in snap.items() if k in (
        "frames", "parameters", "teaching_strategy", "topic", "audience", "difficulty",
        "project_id", "assets", "export_targets",
    )}

    # 2. 构建初始 state（跳过 planner + knowledge，已有其产出）
    state: AgentState = {
        "user_input": snap.get("topic", snap.get("input_content", "")),
        "project_id": project_id,
        "teaching_plan": teaching_plan,
        "knowledge_graph": knowledge_graph,
        "dsl": existing_dsl,
        "constraints": snap.get("constraints", {}),
        "materials": [],
        "approval_mode": False,
        "locked_frame_ids": locked_frame_ids,
        "status": "generating",
        "reflection_count": 0,
        "revision_history": [],
    }

    logger.info("Regenerate: 开始 | project=%s | locked=%d | existing_frames=%d",
                project_id, len(locked_frame_ids),
                len(existing_dsl.get("frames", [])))

    try:
        # 3. Coder
        yield _sse_event("progress", {
            "phase": "coder",
            "message": "正在重新生成帧...",
            "pct": 30,
        })
        coder_result = await coder_node(state)
        state.update(coder_result)
        dsl = state.get("dsl", {})
        yield _sse_event("progress", {
            "phase": "generating",
            "message": f"已完成 {len(dsl.get('frames', []))} 帧生成",
            "pct": 70,
            "frame_count": len(dsl.get("frames", [])),
        })

        # 4. Quality → Reflection loop
        max_cycles = settings.max_reflection_cycles
        for cycle in range(max_cycles + 1):
            yield _sse_event("progress", {
                "phase": "quality",
                "message": "正在校验质量...",
                "pct": 75,
            })
            q_result = await quality_node(state)
            state.update(q_result)
            quality_report = state.get("quality_report", {})
            overall = quality_report.get("overall_score", 1.0)
            is_blocking = quality_report.get("is_blocking", False)

            yield _sse_event("progress", {
                "phase": "validating",
                "message": f"质量校验完成 (score={overall:.2f})",
                "pct": 90,
                "quality_report": quality_report,
            })

            if (overall < settings.quality_score_threshold or is_blocking) and cycle < max_cycles:
                logger.info("Regenerate Reflection 第 %d/%d 次 (score=%.2f)",
                            cycle + 1, max_cycles, overall)
                yield _sse_event("progress", {
                    "phase": "reflection",
                    "message": f"正在修订 (第 {cycle + 1} 次)...",
                    "pct": 85,
                })
                r_result = await reflection_node(state)
                state.update(r_result)
                state["reflection_count"] = cycle + 1
            else:
                break

        # 5. 持久化
        dsl = state.get("dsl", {})
        quality_report = state.get("quality_report", {})
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
                    await save_version(project_id, dsl, f"局部重生成 ({scope.get('type', 'from_frame')})", db_session)
                    await db_session.commit()
        except Exception as perr:
            logger.warning("Regenerate 持久化失败: %s", perr)

        yield _sse_event("done", {
            "phase": "done",
            "pct": 100,
            "dsl": dsl,
            "quality_report": quality_report,
        })

    except Exception as exc:
        logger.exception("Regenerate 失败")
        yield _sse_event("error", {
            "phase": "error",
            "message": f"重生成失败: {exc}",
            "error_code": "REGENERATE_FAILED",
        })


async def _save_interim_teaching_plan(project_id: str, teaching_plan: dict) -> None:
    """HITL 中断时：将 teaching_plan 持久化到 DB，避免切 Tab 后丢失。"""
    try:
        from db.database import async_session_factory
        from db.models import Project as ProjectModel
        from api.deps import parse_project_id

        async with async_session_factory() as db_session:
            project = await db_session.get(ProjectModel, parse_project_id(project_id))
            if project is not None:
                snap = dict(project.dsl_snapshot or {})
                snap["teaching_plan"] = teaching_plan
                project.dsl_snapshot = snap
                await db_session.commit()
    except Exception as exc:
        logger.warning("teaching_plan 暂存失败: %s", exc)


async def _drive_graph(
    graph,
    graph_input,
    config: dict[str, Any],
    project_id: str,
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


async def run_module_generation_stream(
    project_id: str,
    selected_modules: list[str],
) -> AsyncGenerator[str, None]:
    """执行模块化生成流程并以 SSE 格式流式推送进度。

    从 DB 读取已审批的 teaching_plan / knowledge_graph 等上下文，
    通过 ModuleDispatcher 调度用户选中的模块生成器。

    Args:
        project_id: 项目 ID
        selected_modules: 用户选中的模块 ID 列表
    """
    from agents.state import AgentState
    from services.module_dispatcher import dispatch_modules
    from db.database import async_session_factory
    from db.models import Project as ProjectModel
    from api.deps import parse_project_id

    # 从 DB 读取上下文
    async with async_session_factory() as db_session:
        project = await db_session.get(ProjectModel, parse_project_id(project_id))
        if project is None:
            yield _sse_event("error", {
                "phase": "error",
                "message": "项目不存在",
                "error_code": "NOT_FOUND",
            })
            return

        snap = project.dsl_snapshot or {}
        teaching_plan = snap.get("teaching_plan", {})
        knowledge_graph = snap.get("knowledge_graph", {})
        user_input = snap.get("input_content", snap.get("topic", ""))
        constraints = snap.get("constraints", {})

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

    logger.info("模块生成流启动: project=%s modules=%s", project_id, selected_modules)

    try:
        async for chunk in dispatch_modules(
            project_id=project_id,
            state=state,
            selected_modules=selected_modules,
        ):
            yield chunk
    except Exception:
        logger.exception("模块生成流程失败")
        yield _sse_event("error", {
            "phase": "error",
            "message": "模块生成流程内部错误，请稍后重试",
            "error_code": "MODULE_GENERATION_FAILED",
        })


# ── Helpers ─────────────────────────────────────────────────


def _sse_event(event: str, data: dict[str, Any]) -> dict[str, str]:
    """构建 SSE 事件（返回 dict，由 sse-starlette EventSourceResponse 编码）。

    sse-starlette 3.x 对 string 会二次包 data: → 前端收不到。
    返 dict({"event": ..., "data": json.dumps(...)}) 由 sse-starlette 正确格式化。
    """
    return {"event": event, "data": json.dumps(data, ensure_ascii=False)}


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
