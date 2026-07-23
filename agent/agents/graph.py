"""LangGraph Agent 编排图。

5 Agent 协作:
    Planner → Knowledge → Coder → Quality → [Reflection → Coder] → END

支持:
- Postgres checkpointer 持久化（生产环境）
- 内存 checkpointer 降级（开发/测试环境）

对齐设计文档 3.2 节流程图。
"""

from __future__ import annotations

import logging
from typing import Any, Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph

from .state import AgentState
from config import get_settings

logger = logging.getLogger(__name__)

# checkpointer 单例（连接复用）
_checkpointer = None
_checkpointer_initialized = False

# ── 延迟导入（避免在没有 langgraph 时崩溃）──────────────────

_END = None
_StateGraph = None
_planner_node = None
_knowledge_node = None
_coder_node = None
_quality_node = None
_reflection_node = None


def _get_end():
    global _END
    if _END is None:
        from langgraph.graph import END
        _END = END
    return _END


def _get_state_graph():
    global _StateGraph
    if _StateGraph is None:
        from langgraph.graph import StateGraph
        _StateGraph = StateGraph
    return _StateGraph


def _get_planner_node():
    global _planner_node
    if _planner_node is None:
        from .nodes import planner_node
        _planner_node = planner_node
    return _planner_node


def _get_coder_node():
    global _coder_node
    if _coder_node is None:
        from .nodes import coder_node
        _coder_node = coder_node
    return _coder_node


def _get_knowledge_node():
    global _knowledge_node
    if _knowledge_node is None:
        from .nodes import knowledge_node
        _knowledge_node = knowledge_node
    return _knowledge_node


def _get_quality_node():
    global _quality_node
    if _quality_node is None:
        from .nodes import quality_node
        _quality_node = quality_node
    return _quality_node


def _get_reflection_node():
    global _reflection_node
    if _reflection_node is None:
        from .nodes import reflection_node
        _reflection_node = reflection_node
    return _reflection_node


# ── 条件路由 ────────────────────────────────────────────────


def _should_continue_after_planner(state: AgentState) -> Literal["knowledge", "__end__"]:
    """Planner 完成后：被拒绝则结束（等前端重启），否则进入 Knowledge。

    HITL 审批本身由 planner_node 内的运行期 ``interrupt()`` 处理（见 nodes.py），
    这里只在「拒绝」时短路到 END。
    """
    if state.get("plan_rejected"):
        return "__end__"
    return "knowledge"


def _should_reflect(state: AgentState) -> Literal["reflection", "__end__"]:
    """Quality 完成后：是否触发 Reflection。"""
    settings = get_settings()
    report = state.get("quality_report", {})
    overall = report.get("overall_score", 1.0)
    is_blocking = report.get("is_blocking", False)
    count = state.get("reflection_count", 0)
    max_cycles = settings.max_reflection_cycles

    if (overall < settings.quality_score_threshold or is_blocking) and count < max_cycles:
        logger.info("Quality %.2f < %.2f, 触发 Reflection (第 %d/%d 次)",
                    overall, settings.quality_score_threshold, count + 1, max_cycles)
        return "reflection"
    return "__end__"


def _after_reflection(state: AgentState) -> Literal["coder", "__end__"]:
    """Reflection 完成后：回到 Coder 重生成。"""
    settings = get_settings()
    count = state.get("reflection_count", 0)
    if count >= settings.max_reflection_cycles:
        logger.warning("Reflection 已达上限 %d 次，终止循环", count)
        return "__end__"
    return "coder"


# ── Graph 构建 ──────────────────────────────────────────────


def build_graph(checkpointer=None) -> "CompiledStateGraph":
    """构建 LangGraph StateGraph。

    流程:
        START → Planner → Knowledge → Coder → Quality → [Reflection → Coder] → END

    Human-in-the-Loop:
        Planner 输出后可通过 pending_approval 中断。

    Args:
        checkpointer: LangGraph checkpointer 实例。None 时使用内存模式。
    """
    StateGraph = _get_state_graph()
    END = _get_end()

    workflow = StateGraph(AgentState)

    # 注册节点
    workflow.add_node("planner", _get_planner_node())
    workflow.add_node("knowledge", _get_knowledge_node())
    workflow.add_node("coder", _get_coder_node())
    workflow.add_node("quality", _get_quality_node())
    workflow.add_node("reflection", _get_reflection_node())

    # 入口
    workflow.set_entry_point("planner")

    # Planner → Knowledge（拒绝则 END；HITL 审批由 planner_node 内 interrupt() 处理）
    workflow.add_conditional_edges(
        "planner",
        _should_continue_after_planner,
        {"knowledge": "knowledge", "__end__": END},
    )

    # Knowledge → Coder
    workflow.add_edge("knowledge", "coder")

    # Coder → Quality
    workflow.add_edge("coder", "quality")

    # Quality → Reflection 或 END
    workflow.add_conditional_edges(
        "quality",
        _should_reflect,
        {"reflection": "reflection", "__end__": END},
    )

    # Reflection → Coder (重生成) 或 END
    workflow.add_conditional_edges(
        "reflection",
        _after_reflection,
        {"coder": "coder", "__end__": END},
    )

    compile_kwargs: dict[str, Any] = {}
    if checkpointer is not None:
        compile_kwargs["checkpointer"] = checkpointer
        logger.info("Graph 使用 checkpointer: %s", type(checkpointer).__name__)

    return workflow.compile(**compile_kwargs)


# 全局编译好的 graph 实例
_graph: "CompiledStateGraph | None" = None

# Postgres checkpointer 的 AsyncExitStack（进程生命周期内持有连接，不退出）
_checkpointer_stack = None


def _memory_checkpointer():
    """创建 MemorySaver 兜底 checkpointer。"""
    try:
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()
    except ImportError:
        logger.warning("MemorySaver 不可用，aget_state 将不可用")
        return None


def _postgres_db_url() -> str:
    """返回 LangGraph AsyncPostgresSaver 需要的纯 postgresql:// URL。"""
    from config import get_settings
    db_url = get_settings().database_url
    # SQLAlchemy 用 postgresql+asyncpg://，langgraph 用纯 postgresql://
    return db_url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def get_graph_async() -> "CompiledStateGraph":
    """异步获取全局 Agent 编排图（在请求上下文中 await）。

    首次调用时初始化 Postgres checkpointer（跨请求/重启持久化 interrupt 状态）；
    不可用时回落 MemorySaver。之后复用单例。

    注意：实际图构建委托给 get_graph()，以便测试对 get_graph 的 patch 生效。
    """
    global _checkpointer, _checkpointer_initialized, _checkpointer_stack

    if _graph is not None:
        return _graph

    if not _checkpointer_initialized:
        _checkpointer_initialized = True
        try:
            import asyncio as _asyncio
            from contextlib import AsyncExitStack
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

            stack = AsyncExitStack()
            # from_conn_string 返回 async 上下文管理器 —— 用 ExitStack 进入拿到真正的 saver
            # 加 5s 超时：Postgres 没运行时快速回落 MemorySaver，避免 SSE 流静默卡死
            saver = await _asyncio.wait_for(
                stack.enter_async_context(
                    AsyncPostgresSaver.from_conn_string(_postgres_db_url())
                ),
                timeout=5.0,
            )
            await _asyncio.wait_for(saver.setup(), timeout=5.0)
            _checkpointer = saver
            _checkpointer_stack = stack  # 进程存活期间保持连接
            logger.info("Postgres checkpointer 已初始化")
        except ImportError:
            logger.info("langgraph-checkpoint-postgres 未安装，使用内存 checkpointer")
        except Exception as exc:
            logger.warning("Postgres checkpointer 初始化失败（%s），使用内存模式", exc)

    if _checkpointer is None:
        _checkpointer = _memory_checkpointer()

    # 复用同步入口构建/返回单例（保持 checkpointer 已初始化状态）
    return get_graph()


def get_graph() -> "CompiledStateGraph":
    """同步获取全局 Agent 编排图（无事件循环场景 / 测试）。

    使用已初始化的 checkpointer；未初始化时用 MemorySaver（同步可用）。
    """
    global _graph, _checkpointer, _checkpointer_initialized

    if _graph is not None:
        return _graph

    if _checkpointer is None:
        _checkpointer = _memory_checkpointer()
    _checkpointer_initialized = True
    _graph = build_graph(checkpointer=_checkpointer)
    return _graph


async def close_checkpointer() -> None:
    """关闭 Postgres checkpointer 连接（应用关闭时调用）。"""
    global _checkpointer_stack
    if _checkpointer_stack is not None:
        try:
            await _checkpointer_stack.aclose()
        except Exception as exc:
            logger.warning("关闭 checkpointer 失败: %s", exc)
        finally:
            _checkpointer_stack = None
