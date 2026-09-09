"""LangGraph Agent 编排图。

5 Agent 协作:
    Planner → Knowledge → (Coder → Quality ↔ Reflection | Module DAG) → END

支持:
- Postgres checkpointer 持久化（生产环境）
- 内存 checkpointer 降级（开发/测试环境）

对齐设计文档 3.2 节流程图。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph

from config import get_settings

from .state import AgentState

logger = logging.getLogger(__name__)

# checkpointer 单例（连接复用）
_checkpointer = None
_checkpointer_initialized = False

# ── 延迟导入（避免在没有 langgraph 时崩溃）──────────────────

_END = None
_START = None
_StateGraph = None
# Explicit node overrides used by integration tests and runtime adapters. These
# are not caches: ``None`` always resolves the current function from nodes.py.
_planner_node = None
_knowledge_node = None
_coder_node = None
_quality_node = None
_reflection_node = None
_modules_node = None


def _get_end():
    global _END
    if _END is None:
        from langgraph.graph import END
        _END = END
    return _END


def _get_start():
    global _START
    if _START is None:
        from langgraph.graph import START
        _START = START
    return _START


def _get_state_graph():
    global _StateGraph
    if _StateGraph is None:
        from langgraph.graph import StateGraph
        _StateGraph = StateGraph
    return _StateGraph


def _get_planner_node():
    # Python already caches the imported module. Resolve the function on every
    # graph build so dependency overrides (tests and future runtime adapters)
    # cannot be defeated by a stale process-global function reference.
    if _planner_node is not None:
        return _planner_node
    from .nodes import planner_node
    return planner_node


def _get_coder_node():
    if _coder_node is not None:
        return _coder_node
    from .nodes import coder_node
    return coder_node


def _get_knowledge_node():
    if _knowledge_node is not None:
        return _knowledge_node
    from .nodes import knowledge_node
    return knowledge_node


def _get_quality_node():
    if _quality_node is not None:
        return _quality_node
    from .nodes import quality_node
    return quality_node


def _get_reflection_node():
    if _reflection_node is not None:
        return _reflection_node
    from .nodes import reflection_node
    return reflection_node


def _get_modules_node():
    if _modules_node is not None:
        return _modules_node
    from .nodes import modules_node
    return modules_node


# ── 条件路由 ────────────────────────────────────────────────


def _should_continue_after_planner(
    state: AgentState,
) -> Literal["planner", "knowledge", "__end__"]:
    """Planner 完成后：被拒绝则结束（等前端重启），否则进入 Knowledge。

    HITL 审批本身由 planner_node 内的运行期 ``interrupt()`` 处理（见 nodes.py），
    这里只在「拒绝」时短路到 END。
    """
    if state.get("plan_rejected"):
        if state.get("replan_count", 0) <= get_settings().max_replan_cycles:
            return "planner"
        return "__end__"
    return "knowledge"


def _route_entry(
    state: AgentState,
) -> Literal["planner", "knowledge", "coder", "reflection", "modules"]:
    """Route all supported commands through the canonical workflow graph."""
    entry = state.get("workflow_entry", "planner")
    if entry in {"planner", "knowledge", "coder", "reflection", "modules"}:
        return entry
    return "planner"


def _route_after_knowledge(state: AgentState) -> Literal["modules", "coder"]:
    return "modules" if state.get("selected_modules") else "coder"


def _should_reflect(state: AgentState) -> Literal["reflection", "__end__"]:
    """Quality 完成后：是否触发 Reflection。"""
    from .workflow_policy import needs_reflection

    if needs_reflection(state):
        return "reflection"
    return "__end__"


# ── Graph 构建 ──────────────────────────────────────────────


def build_graph(checkpointer=None) -> "CompiledStateGraph":
    """构建 LangGraph StateGraph。

    流程:
        START → Planner/Knowledge/Coder → Quality ↔ Reflection → END
                                      └→ Module DAG → END

    Human-in-the-Loop:
        Planner 输出后可通过 pending_approval 中断。

    Args:
        checkpointer: LangGraph checkpointer 实例。None 时使用内存模式。
    """
    StateGraph = _get_state_graph()
    END = _get_end()
    START = _get_start()

    workflow = StateGraph(AgentState)

    # 注册节点
    workflow.add_node("planner", _get_planner_node())
    workflow.add_node("knowledge", _get_knowledge_node())
    workflow.add_node("coder", _get_coder_node())
    workflow.add_node("quality", _get_quality_node())
    workflow.add_node("reflection", _get_reflection_node())
    workflow.add_node("modules", _get_modules_node())

    # 正常生成、审批恢复、局部重生成共享一张图，仅入口不同。
    workflow.add_conditional_edges(
        START,
        _route_entry,
        {
            "planner": "planner",
            "knowledge": "knowledge",
            "coder": "coder",
            "reflection": "reflection",
            "modules": "modules",
        },
    )

    # Planner → Knowledge（拒绝则 END；HITL 审批由 planner_node 内 interrupt() 处理）
    workflow.add_conditional_edges(
        "planner",
        _should_continue_after_planner,
        {"planner": "planner", "knowledge": "knowledge", "__end__": END},
    )

    # Knowledge → Module DAG 或传统 Coder
    workflow.add_conditional_edges(
        "knowledge",
        _route_after_knowledge,
        {"modules": "modules", "coder": "coder"},
    )
    workflow.add_edge("modules", END)

    # Coder → Quality
    workflow.add_edge("coder", "quality")

    # Quality → Reflection 或 END
    workflow.add_conditional_edges(
        "quality",
        _should_reflect,
        {"reflection": "reflection", "__end__": END},
    )

    # Reflection 已直接应用局部修订，回到 Quality 复核；不得再次全量 Coder 覆盖修订。
    workflow.add_edge("reflection", "quality")

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
