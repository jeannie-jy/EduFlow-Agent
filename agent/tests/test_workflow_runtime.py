"""Canonical workflow policy and Quality/Reflection runtime tests."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_quality_cycle_reflects_then_rechecks_without_full_coder():
    from services.workflow_runtime import run_quality_reflection_cycle

    state = {"reflection_count": 0, "dsl": {"frames": []}}
    quality = AsyncMock(side_effect=[
        {"quality_report": {"overall_score": 0.2, "is_blocking": True}},
        {"quality_report": {"overall_score": 0.9, "is_blocking": False}},
    ])

    async def reflect(current):
        return {"reflection_count": current.get("reflection_count", 0) + 1}

    settings = SimpleNamespace(quality_score_threshold=0.6, max_reflection_cycles=3)
    with (
        patch("agents.nodes.quality_node", quality),
        patch("agents.nodes.reflection_node", new=AsyncMock(side_effect=reflect)) as reflection,
        patch("agents.workflow_policy.get_settings", return_value=settings),
    ):
        events = await run_quality_reflection_cycle(state)

    assert quality.await_count == 2
    assert reflection.await_count == 1
    assert state["reflection_count"] == 1
    assert [event["phase"] for event in events] == [
        "quality", "validating", "reflection", "quality", "validating"
    ]


def test_graph_returns_reflection_directly_to_quality():
    from agents.graph import build_graph

    graph = build_graph()
    edges = graph.get_graph().edges
    assert any(
        getattr(edge, "source", None) == "reflection"
        and getattr(edge, "target", None) == "quality"
        for edge in edges
    )
    assert not any(
        getattr(edge, "source", None) == "reflection"
        and getattr(edge, "target", None) == "coder"
        for edge in edges
    )


def test_graph_entry_router_supports_full_resume_and_regenerate():
    from agents.graph import _route_entry

    assert _route_entry({}) == "planner"
    assert _route_entry({"workflow_entry": "knowledge"}) == "knowledge"
    assert _route_entry({"workflow_entry": "coder"}) == "coder"
    assert _route_entry({"workflow_entry": "reflection"}) == "reflection"
    assert _route_entry({"workflow_entry": "modules"}) == "modules"
    assert _route_entry({"workflow_entry": "invalid"}) == "planner"


def test_rejected_plan_loops_inside_graph_until_limit():
    from agents.graph import _should_continue_after_planner

    settings = SimpleNamespace(max_replan_cycles=3)
    with patch("agents.graph.get_settings", return_value=settings):
        assert _should_continue_after_planner(
            {"plan_rejected": True, "replan_count": 1}
        ) == "planner"
        assert _should_continue_after_planner(
            {"plan_rejected": True, "replan_count": 4}
        ) == "__end__"


@pytest.mark.asyncio
async def test_modules_node_runs_dependency_scheduler_inside_graph():
    from agents.nodes import modules_node

    async def events(*args, **kwargs):
        yield {
            "event": "done",
            "data": (
                '{"module_outputs":{"frames":{"frames":[{"frame_id":"f1"}]}},'
                '"module_errors":null}'
            ),
        }

    with patch(
        "services.module_dispatcher.dispatch_modules", side_effect=events
    ) as dispatch:
        result = await modules_node(
            {"project_id": "p1", "selected_modules": ["frames"]}
        )

    assert result["status"] == "done"
    assert result["dsl"]["frames"][0]["frame_id"] == "f1"
    assert dispatch.call_args.kwargs["persist_result"] is False


@pytest.mark.asyncio
async def test_modules_node_emits_fine_grained_events_inside_runnable():
    from agents.nodes import modules_node
    from langchain_core.runnables import RunnableLambda

    scheduler_events = [
        {
            "event": "module_start",
            "data": json.dumps(
                {"module_id": "frames", "display_name": "Frames", "pct": 10}
            ),
        },
        {
            "event": "module_done",
            "data": json.dumps(
                {
                    "module_id": "frames",
                    "display_name": "Frames",
                    "output": {"frames": [{"frame_id": "f1"}]},
                    "pct": 90,
                }
            ),
        },
        {
            "event": "done",
            "data": json.dumps(
                {
                    "module_outputs": {
                        "frames": {"frames": [{"frame_id": "f1"}]}
                    },
                    "module_errors": None,
                }
            ),
        },
    ]

    async def events(*args, **kwargs):
        del args, kwargs
        for event in scheduler_events:
            yield event

    with patch("services.module_dispatcher.dispatch_modules", side_effect=events):
        events = [
            event
            async for event in RunnableLambda(modules_node).astream_events(
                {"project_id": "p1", "selected_modules": ["frames"]}, version="v2"
            )
        ]

    custom = [
        event
        for event in events
        if event["event"] == "on_custom_event"
        and event["name"] == "eduflow_module_event"
    ]
    assert [event["data"]["event"] for event in custom] == [
        "module_start",
        "module_done",
    ]
    assert custom[1]["data"]["payload"]["module_id"] == "frames"


@pytest.mark.asyncio
async def test_canonical_graph_persists_interrupt_and_resumes_to_done():
    import agents.graph as graph_module
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.types import Command, interrupt

    async def planner(state):
        decision = interrupt({"teaching_plan": {"objectives": ["learn"]}})
        return {
            "teaching_plan": {"objectives": ["learn"]},
            "plan_rejected": decision.get("action") == "reject",
        }

    async def knowledge(state):
        return {"knowledge_graph": {"concepts": [{"id": "c1"}]}}

    async def coder(state):
        return {"dsl": {"frames": [{"frame_id": "f1"}]}}

    async def quality(state):
        return {"quality_report": {"overall_score": 1.0, "is_blocking": False}}

    with patch.multiple(
        graph_module,
        _planner_node=planner,
        _knowledge_node=knowledge,
        _coder_node=coder,
        _quality_node=quality,
        _reflection_node=AsyncMock(),
        _modules_node=AsyncMock(),
    ):
        graph = graph_module.build_graph(checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": "resume-integration"}}
        await graph.ainvoke(
            {
                "workflow_entry": "planner",
                "user_input": "sorting",
                "approval_mode": True,
                "reflection_count": 0,
                "replan_count": 0,
            },
            config,
        )
        interrupted = await graph.aget_state(config)
        assert interrupted.tasks[0].interrupts

        result = await graph.ainvoke(Command(resume={"action": "approve"}), config)

    assert result["dsl"]["frames"][0]["frame_id"] == "f1"
    assert result["quality_report"]["overall_score"] == 1.0
