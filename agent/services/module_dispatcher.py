"""ModuleDispatcher — 模块生成调度器。

负责：
1. 先运行 Knowledge Node 获取共享的 knowledge_graph
2. 按顺序调度用户选中的模块生成器
3. 以 SSE 事件格式 yield 各模块的生成进度
4. 持久化模块产出到 DB
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator

from agents.state import AgentState

logger = logging.getLogger(__name__)


async def dispatch_modules(
    project_id: str,
    state: AgentState,
    selected_modules: list[str],
) -> AsyncGenerator[dict[str, str], None]:
    """调度选中模块的生成流程，以 SSE 事件格式 yield 进度。

    流程:
      1. Knowledge Node（如果尚未生成 knowledge_graph）
      2. 逐个运行选中模块的 generator
      3. 持久化 module_outputs 到 DB
      4. yield 'done' 事件

    每个模块失败不阻塞其他模块。

    Args:
        project_id: 项目 ID
        state: AgentState（需包含 teaching_plan、user_input 等）
        selected_modules: 用户选中的模块 ID 列表
    """
    from generators.registry import get_generator

    module_outputs: dict[str, Any] = {}
    module_errors: dict[str, str] = {}
    # video 依赖 frames → 自动补充 frames + 强制排在最后
    if "video" in selected_modules and "frames" not in selected_modules:
        selected_modules = list(selected_modules) + ["frames"]
    if "video" in selected_modules:
        selected_modules = [m for m in selected_modules if m != "video"] + ["video"]
    total = len(selected_modules)

    try:
            # ── 1. Knowledge Node：所有模块的共享前置 ──────────────────
        kg = state.get("knowledge_graph")
        if not kg or not kg.get("concepts"):
            yield _sse("progress", {
                "phase": "knowledge",
                "message": "正在构建知识图谱...",
                "pct": 5,
            })
            try:
                from agents.nodes import knowledge_node
                k_result = await knowledge_node(state)
                state.update(k_result)
                kg = state.get("knowledge_graph", {})
                terms = state.get("key_terms", [])
                yield _sse("progress", {
                    "phase": "knowledge",
                    "message": f"知识图谱构建完成 ({len(kg.get('concepts', []))} 概念, {len(terms)} 术语)",
                    "pct": 10,
                    "knowledge_graph": kg,
                })
            except Exception as exc:
                logger.exception("Knowledge Node 失败，使用空知识图谱继续")
                yield _sse("progress", {
                    "phase": "knowledge",
                    "message": f"知识图谱构建失败，部分模块可能降级生成（缺少知识上下文）",
                    "pct": 10,
                })

        # ── 2. 调度模块生成器 ─────────────────────────────────────

        teaching_plan = state.get("teaching_plan", {})
        user_input = state.get("user_input", "")
        constraints = state.get("constraints", {})

        for idx, mod_id in enumerate(selected_modules):
            gen = get_generator(mod_id)
            if gen is None:
                logger.warning("未知模块 '%s'，跳过", mod_id)
                module_errors[mod_id] = f"未知模块: {mod_id}"
                yield _sse("module_error", {
                    "module_id": mod_id,
                    "error": f"未知模块: {mod_id}",
                    "pct": _pct_for_index(idx, total),
                })
                continue

            # 模块开始
            base_pct = _pct_for_index(idx, total)
            yield _sse("module_start", {
                "module_id": mod_id,
                "display_name": gen.display_name,
                "message": f"正在生成 {gen.display_name}...",
                "pct": base_pct,
            })

            try:
                output = await gen.generate(
                    teaching_plan=teaching_plan,
                    knowledge_graph=kg or {},
                    user_input=user_input,
                    constraints=constraints,
                    project_id=project_id,
                    existing_outputs=module_outputs,
                )

                # 校验（severity 语义：high=阻断性错误 / medium=警告 / low=提示）
                issues = gen.validate(output)
                if issues:
                    errors_only = [i for i in issues if i.get("severity") == "high"]
                    warnings_only = [i for i in issues if i.get("severity") != "high"]
                    if errors_only:
                        logger.warning("Module '%s' 校验发现 %d 个 high 级问题: %s",
                                       mod_id, len(errors_only),
                                       "; ".join(i.get("description", "")[:60] for i in errors_only))
                    if warnings_only:
                        logger.info("Module '%s' 校验发现 %d 个警告/提示", mod_id, len(warnings_only))

                module_outputs[mod_id] = output
                yield _sse("module_done", {
                    "module_id": mod_id,
                    "display_name": gen.display_name,
                    "output": output,
                    "issues": issues if issues else None,
                    "pct": _pct_for_index(idx + 1, total),
                })
                logger.info("Module '%s' 生成完成", mod_id)

            except Exception as exc:
                logger.exception("Module '%s' 生成失败", mod_id)
                module_errors[mod_id] = str(exc)[:500]
                yield _sse("module_error", {
                    "module_id": mod_id,
                    "display_name": gen.display_name,
                    "error": str(exc)[:500],
                    "pct": _pct_for_index(idx, total),
                })

        # ── 3. 持久化 ─────────────────────────────────────────────
        try:
            from db.database import async_session_factory
            from db.models import Project as ProjectModel
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
                        None,  # dsl=None，仅更新 module_outputs + module_errors + knowledge_graph
                        teaching_plan=teaching_plan,
                        module_outputs=module_outputs,
                        module_errors=module_errors or None,
                        knowledge_graph=kg,
                    )
                    # frames 模块产出同步写入 frames 表（与 generate_service 路径一致，
                    # 消除「模块流不落表 → frames API 双真源」问题）
                    frames_out = module_outputs.get("frames")
                    if isinstance(frames_out, dict) and frames_out.get("frames"):
                        await persist_frames_to_table(
                            project_id, frames_out.get("frames", []), db_session
                        )
                    # 状态机：有产出 → done；全部失败 → failed；均无 → 维持原状态
                    if module_outputs:
                        project.status = "done"
                    elif module_errors:
                        project.status = "failed"
                    await db_session.commit()
                    logger.info("模块产出已持久化: project=%s modules=%s errors=%s",
                                project_id, list(module_outputs.keys()),
                                list(module_errors.keys()) if module_errors else [])
        except Exception as perr:
            logger.warning("模块产出持久化失败: %s", perr)

    except Exception:
        logger.exception("dispatch_modules 未处理异常")
    finally:
        # ── 4. 完成事件（始终发送，防止僵尸流）───────────────
        yield _sse("done", {
            "phase": "done",
            "pct": 100,
            "module_outputs": module_outputs,
            "module_errors": module_errors if module_errors else None,
            "message": f"已完成 {len(module_outputs)}/{total} 个模块生成"
                + (f"，{len(module_errors)} 个失败" if module_errors else ""),
        })


# ── Helpers ─────────────────────────────────────────────────────


def _sse(event: str, data: dict[str, Any]) -> dict[str, str]:
    """构建 SSE 事件字典（与 generate_service._sse_event 同格式）。"""
    return {"event": event, "data": json.dumps(data, ensure_ascii=False)}


def _pct_for_index(index: int, total: int) -> int:
    """根据模块索引计算进度百分比（10%-90% 区间）。"""
    if total <= 1:
        return 50
    return 10 + int(80 * index / total)
