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
    constraints: dict[str, Any] | None = None,
    materials: list[dict[str, Any]] | None = None,
) -> AsyncGenerator[str, None]:
    """执行生成流程并以 SSE 格式流式推送进度。

    Args:
        project_id: 项目 ID
        user_input: 用户输入主题
        constraints: 教师约束
        materials: 上传材料解析结果
    """
    from agents.graph import get_graph

    graph = get_graph()
    initial_state: AgentState = {
        "user_input": user_input,
        "project_id": project_id,
        "materials": materials or [],
        "constraints": constraints or {},
        "status": "draft",
        "reflection_count": 0,
        "revision_history": [],
    }

    config = {
        "configurable": {
            "thread_id": project_id,
        },
    }

    try:
        async for event in graph.astream_events(initial_state, config=config, version="v2"):
            event_type = event.get("event", "")

            if event_type == "on_chain_start":
                chain_name = event.get("name", "")
                if chain_name in ("planner", "coder", "quality", "reflection"):
                    yield _sse_event("progress", {
                        "phase": chain_name,
                        "message": f"正在执行 {chain_name}...",
                        "pct": _phase_pct(chain_name),
                    })

            elif event_type == "on_chain_end":
                chain_name = event.get("name", "")
                output = event.get("data", {}).get("output", {})

                if chain_name == "planner" and isinstance(output, dict):
                    teaching_plan = output.get("teaching_plan", {})
                    yield _sse_event("progress", {
                        "phase": "planning",
                        "message": "教学计划已生成，等待确认",
                        "pct": 30,
                        "teaching_plan": teaching_plan,
                    })

                elif chain_name == "quality" and isinstance(output, dict):
                    quality_report = output.get("quality_report", {})
                    yield _sse_event("progress", {
                        "phase": "validating",
                        "message": "质量校验完成",
                        "pct": 90,
                        "quality_report": quality_report,
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

        # 获取最终状态
        try:
            final_state = await graph.aget_state(config)
            if final_state and final_state.values:
                dsl = final_state.values.get("dsl", {})
                quality_report = final_state.values.get("quality_report", {})
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

    except Exception as exc:
        logger.exception("生成流程失败")
        yield _sse_event("error", {
            "phase": "error",
            "message": "生成流程内部错误，请稍后重试",
            "error_code": "GENERATION_FAILED",
        })


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
        "coder": 50,
        "quality": 80,
        "reflection": 85,
    }
    return mapping.get(phase, 50)
