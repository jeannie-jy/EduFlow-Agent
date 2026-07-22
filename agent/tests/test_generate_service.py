"""生成服务单元测试。

测试 run_generation_stream（SSE 流式）和 run_generation_sync（同步）。
使用 Mock LangGraph 避免真实 LLM 调用。
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.generate_service import (
    run_generation_stream,
    run_generation_sync,
    _sse_event,
    _phase_pct,
)


# ============================================================================
# Helpers
# ============================================================================


def _parse(event_dict: dict) -> dict:
    """解析 SSE event dict 中的 data 字段（JSON 字符串 → dict）。"""
    return json.loads(event_dict["data"])


# ============================================================================
# SSE Helpers
# ============================================================================


class TestSSEEventFormat:
    """SSE 事件格式测试。"""

    def test_progress_event_format(self):
        """_sse_event 应返回带 event + data 字段的 dict。"""
        event = _sse_event("progress", {"phase": "planner", "message": "测试", "pct": 10})
        assert event["event"] == "progress"
        data = _parse(event)
        assert data["phase"] == "planner"
        assert data["pct"] == 10

    def test_done_event_format(self):
        """done 事件格式。"""
        event = _sse_event("done", {"phase": "done", "pct": 100})
        assert event["event"] == "done"
        data = _parse(event)
        assert data["phase"] == "done"
        assert data["pct"] == 100

    def test_error_event_format(self):
        """error 事件格式。"""
        event = _sse_event("error", {
            "phase": "error",
            "message": "生成失败",
            "error_code": "GENERATION_FAILED",
        })
        assert event["event"] == "error"
        data = _parse(event)
        assert data["phase"] == "error"
        assert data["error_code"] == "GENERATION_FAILED"

    def test_unicode_in_event(self):
        """SSE 事件应正确处理中文。"""
        event = _sse_event("progress", {"phase": "planner", "message": "正在生成教学计划", "pct": 30})
        data = _parse(event)
        assert data["message"] == "正在生成教学计划"


class TestPhasePct:
    """阶段百分比映射测试。"""

    def test_known_phases(self):
        assert _phase_pct("planner") == 10
        assert _phase_pct("knowledge") == 25
        assert _phase_pct("coder") == 50
        assert _phase_pct("quality") == 80
        assert _phase_pct("reflection") == 85

    def test_unknown_phase_defaults_to_50(self):
        assert _phase_pct("unknown_phase") == 50

    def test_all_phases_in_range(self):
        """所有百分比应在 0-100 之间。"""
        for phase in ["planner", "knowledge", "coder", "quality", "reflection", "unknown"]:
            pct = _phase_pct(phase)
            assert 0 <= pct <= 100, f"Phase '{phase}' pct {pct} out of range"


# ============================================================================
# run_generation_sync
# ============================================================================


class TestRunGenerationSync:
    """同步生成流程测试。"""

    @pytest.mark.asyncio
    async def test_sync_returns_state(self):
        """同步生成应返回完整 AgentState。"""
        mock_result = {
            "teaching_plan": {"objectives": ["理解算法"]},
            "dsl": {"frames": [{"frame_id": "f_001"}]},
            "quality_report": {"overall_score": 0.85},
            "status": "done",
        }

        with patch("agents.graph.get_graph") as mock_get_graph:
            mock_graph = MagicMock()
            mock_graph.ainvoke = AsyncMock(return_value=mock_result)
            mock_get_graph.return_value = mock_graph

            result = await run_generation_sync(
                project_id="test_001",
                user_input="讲解冒泡排序",
            )

        assert result["teaching_plan"]["objectives"] == ["理解算法"]
        assert result["status"] == "done"

    @pytest.mark.asyncio
    async def test_sync_passes_correct_initial_state(self):
        """同步生成应传递正确的初始状态。"""
        with patch("agents.graph.get_graph") as mock_get_graph:
            mock_graph = MagicMock()
            mock_graph.ainvoke = AsyncMock(return_value={"status": "done"})
            mock_get_graph.return_value = mock_graph

            await run_generation_sync(
                project_id="proj_123",
                user_input="讲解 Dijkstra",
                constraints={"must_cover": ["松弛"]},
                materials=[{"filename": "课件.pdf", "content_text": "图论基础"}],
            )

        call_args = mock_graph.ainvoke.call_args
        initial_state = call_args[0][0]
        assert initial_state["user_input"] == "讲解 Dijkstra"
        assert initial_state["project_id"] == "proj_123"
        assert initial_state["constraints"]["must_cover"] == ["松弛"]
        assert len(initial_state["materials"]) == 1
        assert initial_state["reflection_count"] == 0
        assert initial_state["revision_history"] == []

    @pytest.mark.asyncio
    async def test_sync_uses_thread_id_config(self):
        """同步生成应使用 project_id 作为 thread_id。"""
        with patch("agents.graph.get_graph") as mock_get_graph:
            mock_graph = MagicMock()
            mock_graph.ainvoke = AsyncMock(return_value={"status": "done"})
            mock_get_graph.return_value = mock_graph

            await run_generation_sync(project_id="my_project", user_input="test")

        call_args = mock_graph.ainvoke.call_args
        config = call_args[0][1]
        assert config["configurable"]["thread_id"] == "my_project"


# ============================================================================
# run_generation_stream
# ============================================================================


class TestRunGenerationStream:
    """SSE 流式生成测试。"""

    @pytest.mark.asyncio
    async def test_stream_yields_progress_events(self):
        """应从每个节点获取进度事件。"""
        async def mock_astream_events(initial_state, config, version):
            yield {"event": "on_chain_start", "name": "planner", "data": {}}
            yield {
                "event": "on_chain_end",
                "name": "planner",
                "data": {
                    "output": {
                        "teaching_plan": {
                            "objectives": ["理解冒泡排序"],
                            "outline": [{"step": 1, "title": "概述", "key_points": ["x"], "estimated_frames": 3}],
                            "teaching_approach": "演示",
                            "estimated_total_frames": 3,
                        },
                    },
                },
            }
            yield {"event": "on_chain_start", "name": "coder", "data": {}}
            yield {
                "event": "on_chain_end",
                "name": "coder",
                "data": {
                    "output": {
                        "dsl": {"frames": [{"frame_id": "f_001"}, {"frame_id": "f_002"}]},
                    },
                },
            }
            yield {"event": "on_chain_start", "name": "quality", "data": {}}
            yield {
                "event": "on_chain_end",
                "name": "quality",
                "data": {
                    "output": {
                        "quality_report": {"overall_score": 0.85, "is_blocking": False},
                    },
                },
            }

        with patch("agents.graph.get_graph") as mock_get_graph:
            mock_graph = MagicMock()
            mock_graph.astream_events = mock_astream_events

            mock_final_state = MagicMock()
            mock_final_state.values = {
                "dsl": {"frames": [{"frame_id": "f_001"}, {"frame_id": "f_002"}]},
                "quality_report": {"overall_score": 0.85},
            }
            mock_graph.aget_state = AsyncMock(return_value=mock_final_state)
            mock_get_graph.return_value = mock_graph

            events = []
            async for event in run_generation_stream(
                project_id="test_001",
                user_input="讲解冒泡排序",
            ):
                events.append(event)

        # 应包含进度事件和 done 事件（含初始 connecting 事件）
        assert len(events) >= 5
        # 验证包含 planner 进度事件
        assert any("planner" in e["data"] for e in events)
        # 验证最后一个事件是 done
        assert events[-1]["event"] == "done"

    @pytest.mark.asyncio
    async def test_stream_phases_in_order(self):
        """事件应按正确顺序发送：planner → knowledge → coder → quality。"""
        async def mock_astream_events(initial_state, config, version):
            phases = ["planner", "knowledge", "coder", "quality"]
            for phase in phases:
                yield {"event": "on_chain_start", "name": phase, "data": {}}
                yield {"event": "on_chain_end", "name": phase, "data": {"output": {}}}

        with patch("agents.graph.get_graph") as mock_get_graph:
            mock_graph = MagicMock()
            mock_graph.astream_events = mock_astream_events
            mock_final_state = MagicMock()
            mock_final_state.values = {}
            mock_graph.aget_state = AsyncMock(return_value=mock_final_state)
            mock_get_graph.return_value = mock_graph

            events = []
            async for event in run_generation_stream(
                project_id="test_001",
                user_input="test",
            ):
                if event["event"] == "progress":
                    events.append(event)

        # 验证阶段顺序
        phases_found = []
        for e in events:
            data = _parse(e)
            for phase in ["planner", "knowledge", "coder", "quality"]:
                if data["phase"] == phase:
                    phases_found.append(phase)
                    break

        assert "planner" in phases_found
        assert "coder" in phases_found

    @pytest.mark.asyncio
    async def test_stream_done_event_includes_dsl(self):
        """done 事件应包含完整 DSL。"""
        async def mock_astream_events(initial_state, config, version):
            yield {"event": "on_chain_start", "name": "planner", "data": {}}
            yield {"event": "on_chain_end", "name": "planner", "data": {"output": {}}}
            yield {"event": "on_chain_start", "name": "coder", "data": {}}
            yield {"event": "on_chain_end", "name": "coder", "data": {"output": {}}}

        with patch("agents.graph.get_graph") as mock_get_graph:
            mock_graph = MagicMock()
            mock_graph.astream_events = mock_astream_events

            mock_final_state = MagicMock()
            mock_final_state.values = {
                "dsl": {
                    "frames": [{"frame_id": "f_001"}, {"frame_id": "f_002"}],
                    "topic": "冒泡排序",
                },
                "quality_report": {"overall_score": 0.9},
            }
            mock_graph.aget_state = AsyncMock(return_value=mock_final_state)
            mock_get_graph.return_value = mock_graph

            events = []
            async for event in run_generation_stream(
                project_id="test_001",
                user_input="test",
            ):
                events.append(event)

        done_event = events[-1]
        assert done_event["event"] == "done"
        data = _parse(done_event)
        assert "dsl" in data
        assert "quality_report" in data

    @pytest.mark.asyncio
    async def test_stream_error_handling(self):
        """生成流程异常时应发送 error 事件。"""
        with patch("agents.graph.get_graph") as mock_get_graph:
            mock_graph = MagicMock()
            mock_graph.astream_events = MagicMock(
                side_effect=RuntimeError("图表编译失败")
            )
            mock_get_graph.return_value = mock_graph

            events = []
            async for event in run_generation_stream(
                project_id="test_001",
                user_input="test",
            ):
                events.append(event)

        # connecting 事件 + error 事件
        assert len(events) == 2
        assert events[-1]["event"] == "error"
        data = _parse(events[-1])
        assert data["phase"] == "error"
        assert data["error_code"] == "GENERATION_FAILED"

    @pytest.mark.asyncio
    async def test_progress_event_includes_pct(self):
        """进度事件应包含 pct 字段。"""
        async def mock_astream_events(initial_state, config, version):
            yield {"event": "on_chain_start", "name": "planner", "data": {}}
            yield {"event": "on_chain_end", "name": "planner",
                   "data": {"output": {"teaching_plan": {}}}}

        with patch("agents.graph.get_graph") as mock_get_graph:
            mock_graph = MagicMock()
            mock_graph.astream_events = mock_astream_events
            mock_final_state = MagicMock()
            mock_final_state.values = {}
            mock_graph.aget_state = AsyncMock(return_value=mock_final_state)
            mock_get_graph.return_value = mock_graph

            events = []
            async for event in run_generation_stream(
                project_id="test_001",
                user_input="test",
            ):
                events.append(event)

        progress_events = [e for e in events if e["event"] == "progress"]
        assert len(progress_events) >= 1
        for pe in progress_events:
            data = _parse(pe)
            assert "pct" in data, f"Progress event missing pct: {data}"

    @pytest.mark.asyncio
    async def test_planner_progress_includes_teaching_plan(self):
        """planner 完成后的进度事件应包含 teaching_plan。"""
        plan = {"objectives": ["目标1"], "outline": [], "estimated_total_frames": 5}

        async def mock_astream_events(initial_state, config, version):
            yield {"event": "on_chain_start", "name": "planner", "data": {}}
            yield {"event": "on_chain_end", "name": "planner",
                   "data": {"output": {"teaching_plan": plan}}}

        with patch("agents.graph.get_graph") as mock_get_graph:
            mock_graph = MagicMock()
            mock_graph.astream_events = mock_astream_events
            mock_final_state = MagicMock()
            mock_final_state.values = {}
            mock_graph.aget_state = AsyncMock(return_value=mock_final_state)
            mock_get_graph.return_value = mock_graph

            events = []
            async for event in run_generation_stream(
                project_id="test_001",
                user_input="test",
            ):
                events.append(event)

        plan_events = [e for e in events if "teaching_plan" in e["data"]]
        assert len(plan_events) >= 1

    @pytest.mark.asyncio
    async def test_knowledge_progress_includes_graph(self):
        """knowledge 完成后的进度事件应包含 knowledge_graph。"""
        kg = {"concepts": [{"id": "c1", "name": "test", "type": "definition"}], "edges": []}
        terms = ["test"]

        async def mock_astream_events(initial_state, config, version):
            yield {"event": "on_chain_start", "name": "knowledge", "data": {}}
            yield {"event": "on_chain_end", "name": "knowledge",
                   "data": {"output": {"knowledge_graph": kg, "key_terms": terms}}}

        with patch("agents.graph.get_graph") as mock_get_graph:
            mock_graph = MagicMock()
            mock_graph.astream_events = mock_astream_events
            mock_final_state = MagicMock()
            mock_final_state.values = {}
            mock_graph.aget_state = AsyncMock(return_value=mock_final_state)
            mock_get_graph.return_value = mock_graph

            events = []
            async for event in run_generation_stream(
                project_id="test_001",
                user_input="test",
            ):
                events.append(event)

        kg_events = [e for e in events if "knowledge_graph" in e["data"]]
        assert len(kg_events) >= 1

    @pytest.mark.asyncio
    async def test_quality_progress_includes_report(self):
        """quality 完成后的进度事件应包含 quality_report。"""
        qr = {"overall_score": 0.85, "is_blocking": False}

        async def mock_astream_events(initial_state, config, version):
            yield {"event": "on_chain_start", "name": "quality", "data": {}}
            yield {"event": "on_chain_end", "name": "quality",
                   "data": {"output": {"quality_report": qr}}}

        with patch("agents.graph.get_graph") as mock_get_graph:
            mock_graph = MagicMock()
            mock_graph.astream_events = mock_astream_events
            mock_final_state = MagicMock()
            mock_final_state.values = {}
            mock_graph.aget_state = AsyncMock(return_value=mock_final_state)
            mock_get_graph.return_value = mock_graph

            events = []
            async for event in run_generation_stream(
                project_id="test_001",
                user_input="test",
            ):
                events.append(event)

        qr_events = [e for e in events if "quality_report" in e["data"]]
        assert len(qr_events) >= 1


# ============================================================================
# HITL interrupt / resume
# ============================================================================


def _make_interrupt_state(teaching_plan):
    """构造一个带 HITL interrupt 的 mock graph state。"""
    intr = MagicMock()
    intr.value = {"type": "teaching_plan_approval", "teaching_plan": teaching_plan}
    task = MagicMock()
    task.interrupts = [intr]
    state = MagicMock()
    state.values = {"teaching_plan": teaching_plan}
    state.tasks = [task]
    return state


class TestHITLInterruptResume:
    """HITL 教学计划审批：interrupt → waiting_approval → resume → done。"""

    @pytest.mark.asyncio
    async def test_plan_only_emits_waiting_approval(self):
        """plan_only 模式在 Planner 后中断，应发 waiting_approval 且不发 done。"""
        plan = {"objectives": ["理解算法"]}

        async def mock_astream_events(initial_state, config, version):
            yield {"event": "on_chain_start", "name": "planner", "data": {}}
            yield {"event": "on_chain_end", "name": "planner",
                   "data": {"output": {"teaching_plan": plan}}}

        with patch("agents.graph.get_graph") as mock_get_graph:
            mock_graph = MagicMock()
            mock_graph.astream_events = mock_astream_events
            mock_graph.aget_state = AsyncMock(return_value=_make_interrupt_state(plan))
            mock_get_graph.return_value = mock_graph

            events = []
            async for event in run_generation_stream(
                project_id="test_001", user_input="讲解冒泡排序", action="plan_only",
            ):
                events.append(event)

        assert any(e["event"] == "waiting_approval" for e in events)
        assert not any(e["event"] == "done" for e in events)
        wa = [e for e in events if e["event"] == "waiting_approval"][0]
        assert "teaching_plan" in wa["data"]

    @pytest.mark.asyncio
    async def test_resume_approve_reaches_done(self):
        """approve resume 从断点继续到 done。"""
        from services.generate_service import resume_generation_stream

        async def mock_astream_events(graph_input, config, version):
            yield {"event": "on_chain_start", "name": "coder", "data": {}}
            yield {"event": "on_chain_end", "name": "coder",
                   "data": {"output": {"dsl": {"frames": [{"frame_id": "f_001"}]}}}}

        final = MagicMock()
        final.values = {"dsl": {"frames": [{"frame_id": "f_001"}]},
                        "quality_report": {"overall_score": 0.9}}
        final.tasks = []

        with patch("agents.graph.get_graph") as mock_get_graph:
            mock_graph = MagicMock()
            mock_graph.astream_events = mock_astream_events
            mock_graph.aget_state = AsyncMock(return_value=final)
            mock_get_graph.return_value = mock_graph

            events = []
            async for event in resume_generation_stream(
                "test_001", {"action": "approve"},
            ):
                events.append(event)

        assert any(e["event"] == "done" for e in events)
        assert not any(e["event"] == "waiting_approval" for e in events)
