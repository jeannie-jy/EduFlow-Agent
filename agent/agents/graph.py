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
    """Planner 完成后：检查是否有 Human-in-the-Loop 审批。"""
    if state.get("pending_approval"):
        return "__end__"  # 使用字符串，由 add_conditional_edges 映射到 END
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

    # Planner → Knowledge (或中断等待审批)
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


def get_graph() -> "CompiledStateGraph":
    """获取全局 Agent 编排图实例。

    首次调用时尝试创建 Postgres checkpointer，失败则使用内存模式。
    """
    global _graph, _checkpointer, _checkpointer_initialized

    if _graph is not None:
        return _graph

    # 尝试创建 Postgres checkpointer
    checkpointer = None
    if not _checkpointer_initialized:
        _checkpointer_initialized = True
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            from config import get_settings

            settings = get_settings()
            # 使用 DATABASE_URL 连接（与 db/database.py 一致）
            db_url = settings.database_url
            # 兼容 postgresql+asyncpg:// → postgresql:// 格式差异
            if db_url.startswith("postgresql+asyncpg://"):
                db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

            import asyncio
            async def _init_checkpointer():
                global _checkpointer
                try:
                    cp = AsyncPostgresSaver.from_conn_string(db_url)
                    await cp.setup()
                    _checkpointer = cp
                    logger.info("Postgres checkpointer 已初始化")
                except Exception as exc:
                    logger.warning("Postgres checkpointer 初始化失败，使用内存模式: %s", exc)

            try:
                loop = asyncio.get_running_loop()
                # 已有事件循环，创建 task（不阻塞）
                import asyncio
                asyncio.ensure_future(_init_checkpointer())
            except RuntimeError:
                # 无事件循环，同步初始化
                asyncio.run(_init_checkpointer())

        except ImportError:
            logger.info("langgraph-checkpoint-postgres 未安装，使用内存 checkpointer")
        except Exception as exc:
            logger.warning("Checkpointer 初始化异常，使用内存模式: %s", exc)

    _graph = build_graph(checkpointer=_checkpointer)
    return _graph
