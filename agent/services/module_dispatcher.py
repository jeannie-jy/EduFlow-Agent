"""ModuleDispatcher — 模块生成调度器。

负责：
1. 先运行 Knowledge Node 获取共享的 knowledge_graph
2. 按顺序调度用户选中的模块生成器
3. 以 SSE 事件格式 yield 各模块的生成进度
4. 持久化模块产出到 DB
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from agents.state import AgentState

logger = logging.getLogger(__name__)


async def dispatch_modules(
    project_id: str,
    state: AgentState,
    selected_modules: list[str],
    *,
    persist_result: bool = True,
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
    module_dependencies: dict[str, list[str]] = {}
    # 通用逐帧 DSL 是所有主题（包括用户自定义算法）的基础交互产物。
    # API 调用方即使没有显式选择，也自动补充；注册检查保留单元测试和
    # 可裁剪部署中不加载 frames generator 的兼容性。
    if "frames" not in selected_modules and get_generator("frames") is not None:
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
            except Exception:
                logger.exception("Knowledge Node 失败，使用空知识图谱继续")
                yield _sse("progress", {
                    "phase": "knowledge",
                    "message": "知识图谱构建失败，部分模块可能降级生成（缺少知识上下文）",
                    "pct": 10,
                })

        # ── 2. 调度模块生成器 ─────────────────────────────────────

        teaching_plan = state.get("teaching_plan", {})
        user_input = state.get("user_input", "")
        constraints = state.get("constraints", {})

        generators = {}
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
            else:
                generators[mod_id] = gen
        module_dependencies = {
            mod_id: list(getattr(generator, "requires", ()))
            for mod_id, generator in generators.items()
        }

        from config import get_settings

        semaphore = asyncio.Semaphore(get_settings().module_generation_concurrency)
        pending = list(generators)
        finished = len(module_errors)
        while pending:
            blocked = [
                mod_id for mod_id in pending
                if any(
                    dependency in module_errors or dependency not in generators
                    for dependency in getattr(generators[mod_id], "requires", ())
                )
            ]
            for mod_id in blocked:
                dependencies = list(getattr(generators[mod_id], "requires", ()))
                error = f"依赖模块未成功: {', '.join(dependencies)}"
                module_errors[mod_id] = error
                pending.remove(mod_id)
                finished += 1
                yield _sse("module_error", {
                    "module_id": mod_id,
                    "display_name": generators[mod_id].display_name,
                    "error": error,
                    "pct": _pct_for_index(finished, total),
                })

            ready = [
                mod_id for mod_id in pending
                if set(getattr(generators[mod_id], "requires", ())) <= set(module_outputs)
            ]
            if not ready and pending:
                for mod_id in list(pending):
                    error = "模块依赖存在循环，无法调度"
                    module_errors[mod_id] = error
                    pending.remove(mod_id)
                    finished += 1
                    yield _sse("module_error", {
                        "module_id": mod_id,
                        "display_name": generators[mod_id].display_name,
                        "error": error,
                        "pct": _pct_for_index(finished, total),
                    })
                break

            existing_outputs = dict(module_outputs)
            for mod_id in ready:
                yield _sse("module_start", {
                    "module_id": mod_id,
                    "display_name": generators[mod_id].display_name,
                    "message": f"正在生成 {generators[mod_id].display_name}...",
                    "pct": _pct_for_index(finished, total),
                })

            results = await asyncio.gather(*(
                _run_module(
                    mod_id,
                    generators[mod_id],
                    semaphore=semaphore,
                    teaching_plan=teaching_plan,
                    knowledge_graph=kg or {},
                    user_input=user_input,
                    constraints=constraints,
                    project_id=project_id,
                    existing_outputs=existing_outputs,
                )
                for mod_id in ready
            ))
            for mod_id, output, issues, error in results:
                pending.remove(mod_id)
                finished += 1
                gen = generators[mod_id]
                if error is not None:
                    module_errors[mod_id] = error
                    yield _sse("module_error", {
                        "module_id": mod_id,
                        "display_name": gen.display_name,
                        "error": error,
                        "pct": _pct_for_index(finished, total),
                    })
                else:
                    module_outputs[mod_id] = output
                    yield _sse("module_done", {
                        "module_id": mod_id,
                        "display_name": gen.display_name,
                        "output": output,
                        "issues": issues or None,
                        "pct": _pct_for_index(finished, total),
                    })
                    logger.info("Module '%s' 生成完成", mod_id)

        # Direct callers retain compatibility. The canonical LangGraph node
        # disables this branch so graph finalization remains the sole writer.
        if persist_result:
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
                    project = await db_session.get(
                        ProjectModel, parse_project_id(project_id)
                    )
                    if project is not None:
                        # frames 模块产出的是完整 DSL 对象 → 提升到快照顶层，
                        # 与 generate_service 全量流一致（导出 API 从顶层读 frames）
                        frames_out = module_outputs.get("frames")
                        frames_dsl = (
                            frames_out
                            if isinstance(frames_out, dict) and frames_out.get("frames")
                            else None
                        )
                        project.dsl_snapshot = merge_dsl_snapshot(
                            project.dsl_snapshot,
                            frames_dsl,
                            teaching_plan=teaching_plan,
                            module_outputs=module_outputs,
                            module_errors=module_errors,
                            knowledge_graph=kg,
                            selected_modules=selected_modules,
                            module_dependencies=module_dependencies,
                        )
                        if frames_dsl is not None:
                            await persist_frames_to_table(
                                project_id, frames_dsl.get("frames", []), db_session
                            )
                        if module_outputs:
                            await save_version(
                                project_id,
                                project.dsl_snapshot,
                                "模块产物生成",
                                db_session,
                            )
                            project.status = "done"
                        elif module_errors:
                            project.status = "failed"
                        await db_session.commit()
                        logger.info(
                            "模块产出已持久化: project=%s modules=%s errors=%s",
                            project_id,
                            list(module_outputs.keys()),
                            list(module_errors.keys()) if module_errors else [],
                        )
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
            "module_dependencies": module_dependencies,
            "message": f"已完成 {len(module_outputs)}/{total} 个模块生成"
                + (f"，{len(module_errors)} 个失败" if module_errors else ""),
        })


# ── Helpers ─────────────────────────────────────────────────────


async def _run_module(mod_id: str, gen, *, semaphore: asyncio.Semaphore, **kwargs):
    try:
        async with semaphore:
            output = await gen.generate(**kwargs)
        issues = gen.validate(output)
        blocking = [issue for issue in issues if issue.get("severity") == "high"]
        if blocking:
            logger.warning("Module '%s' has %d blocking validation issues", mod_id, len(blocking))
        return mod_id, output, issues, None
    except Exception:
        logger.exception("Module '%s' 生成失败", mod_id)
        from services.redaction import public_failure_message

        return mod_id, None, [], public_failure_message("module")


def _sse(event: str, data: dict[str, Any]) -> dict[str, str]:
    """构建 SSE 事件字典（与 generate_service._sse_event 同格式）。"""
    return {"event": event, "data": json.dumps(data, ensure_ascii=False)}


def _pct_for_index(index: int, total: int) -> int:
    """根据模块索引计算进度百分比（10%-90% 区间）。"""
    if total <= 1:
        return 50
    return 10 + int(80 * index / total)
