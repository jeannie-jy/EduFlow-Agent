"""ModuleDispatcher 单元测试。

测试 dispatch_modules() 的编排逻辑：
- 单个模块调度
- 多个模块串行调度
- 未注册模块错误处理
- 模块失败不阻塞其他模块
- Knowledge Node 前置调用
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from generators.registry import clear_registry, register_generator
from services.module_dispatcher import dispatch_modules

# ============================================================================
# Mock Generator（带可控行为）
# ============================================================================


class _MockWorkingGen:
    module_id = "mock_ok"
    display_name = "Mock OK"
    description = "Always succeeds"
    icon = "ok"
    category = "visual"
    priority = 1
    version = "1.0.0"

    async def generate(self, **kwargs):
        return {"status": "ok", "data": "test output"}

    def validate(self, output):
        return []

    def get_output_schema(self):
        return {"type": "object", "properties": {"status": {"type": "string"}}}

    def get_system_prompt(self):
        return "You are a mock generator."


class _MockFailingGen:
    module_id = "mock_fail"
    display_name = "Mock Fail"
    description = "Always fails"
    icon = "fail"
    category = "visual"
    priority = 5
    version = "1.0.0"

    async def generate(self, **kwargs):
        raise RuntimeError("Simulated generator failure")

    def validate(self, output):
        return [{"severity": "high", "type": "broken", "description": "Never gets here"}]

    def get_output_schema(self):
        return {"type": "object"}

    def get_system_prompt(self):
        return "Failing generator."


class _MockSlowGen:
    module_id = "mock_slow"
    display_name = "Mock Slow"
    description = "Slow generator"
    icon = "slow"
    category = "interactive"
    priority = 3
    version = "1.0.0"

    def __init__(self):
        self.call_count = 0

    async def generate(self, **kwargs):
        self.call_count += 1
        return {"status": "done", "call": self.call_count}

    def validate(self, output):
        return []

    def get_output_schema(self):
        return {"type": "object"}

    def get_system_prompt(self):
        return "Slow generator."


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def _clean_registry():
    clear_registry()
    yield
    clear_registry()


def _make_minimal_state(**overrides):
    """构建最小 AgentState。"""
    state = {
        "user_input": "Test topic",
        "project_id": "test-proj-001",
        "teaching_plan": {
            "objectives": ["Test objective"],
            "outline": [{"step": 1, "title": "Intro", "key_points": ["p1"], "estimated_frames": 3}],
            "teaching_approach": "Test approach",
            "estimated_total_frames": 3,
        },
        "knowledge_graph": {
            "concepts": [{"id": "c1", "name": "Test Concept", "type": "definition"}],
            "edges": [],
        },
        "key_terms": ["Test"],
        "constraints": {},
        "materials": [],
        "status": "generating",
        "reflection_count": 0,
        "revision_history": [],
    }
    state.update(overrides)
    return state


# ============================================================================
# Tests: dispatch_modules
# ============================================================================


class TestDispatchModulesBasic:
    """测试基本调度行为。"""

    async def test_dispatch_single_module(self):
        from services.module_dispatcher import dispatch_modules

        register_generator(_MockWorkingGen())
        state = _make_minimal_state()

        events = []
        async for evt in dispatch_modules("test-proj-001", state, ["mock_ok"]):
            events.append(evt)

        phases = {evt["event"] for evt in events}
        assert "module_start" in phases
        assert "module_done" in phases
        assert "done" in phases

    async def test_dispatch_multiple_modules(self):
        from services.module_dispatcher import dispatch_modules

        register_generator(_MockWorkingGen())
        slow_gen = _MockSlowGen()
        register_generator(slow_gen)
        state = _make_minimal_state()

        events = []
        async for evt in dispatch_modules("test-proj-001", state, ["mock_ok", "mock_slow"]):
            events.append(evt)

        done_events = [e for e in events if e["event"] == "module_done"]
        assert len(done_events) == 2

        import json
        module_ids = {json.loads(e["data"])["module_id"] for e in done_events}
        assert module_ids == {"mock_ok", "mock_slow"}

    async def test_dispatch_sends_done_event_last(self):
        from services.module_dispatcher import dispatch_modules

        register_generator(_MockWorkingGen())
        state = _make_minimal_state()

        events = []
        async for evt in dispatch_modules("test-proj-001", state, ["mock_ok"]):
            events.append(evt)

        last = events[-1]
        assert last["event"] == "done"

    async def test_independent_modules_run_with_bounded_concurrency(self):
        active = 0
        peak = 0

        class ConcurrentGen(_MockWorkingGen):
            def __init__(self, module_id):
                self.module_id = module_id

            async def generate(self, **kwargs):
                nonlocal active, peak
                active += 1
                peak = max(peak, active)
                await asyncio.sleep(0.02)
                active -= 1
                return {"status": "ok"}

        for module_id in ("independent_a", "independent_b", "independent_c"):
            register_generator(ConcurrentGen(module_id))
        settings = MagicMock(module_generation_concurrency=2)
        with patch("config.get_settings", return_value=settings):
            events = [
                event async for event in dispatch_modules(
                    "test-proj-001",
                    _make_minimal_state(),
                    ["independent_a", "independent_b", "independent_c"],
                )
            ]
        assert peak == 2
        assert sum(event["event"] == "module_done" for event in events) == 3

    async def test_required_module_runs_in_later_dag_wave(self):
        call_order = []

        class FramesGen(_MockWorkingGen):
            module_id = "frames"

            async def generate(self, **kwargs):
                call_order.append("frames")
                return {"frames": [{"frame_id": "f_001"}]}

        class DependentGen(_MockWorkingGen):
            module_id = "dependent"
            requires = ("frames",)

            async def generate(self, **kwargs):
                assert "frames" in kwargs["existing_outputs"]
                call_order.append("dependent")
                return {"status": "ok"}

        register_generator(FramesGen())
        register_generator(DependentGen())
        events = [
            event async for event in dispatch_modules(
                "test-proj-001", _make_minimal_state(), ["dependent"]
            )
        ]
        assert call_order == ["frames", "dependent"]
        assert json.loads(events[-1]["data"])["module_errors"] is None


class TestDispatchModulesErrors:
    """测试错误处理。"""

    async def test_module_failure_does_not_block_others(self):
        from services.module_dispatcher import dispatch_modules

        register_generator(_MockWorkingGen())
        register_generator(_MockFailingGen())
        state = _make_minimal_state()

        events = []
        async for evt in dispatch_modules("test-proj-001", state, ["mock_fail", "mock_ok"]):
            events.append(evt)

        # mock_fail 应该产生 error 事件，mock_ok 应该正常完成
        import json
        error_events = [e for e in events if e["event"] == "module_error"]
        done_events = [e for e in events if e["event"] == "module_done"]

        assert len(error_events) >= 1
        assert len(done_events) >= 1  # mock_ok still completes

        error_data = json.loads(error_events[0]["data"])
        assert error_data["module_id"] == "mock_fail"
        assert error_data["error"] == "模块生成失败，请稍后重试"
        assert "Simulated generator failure" not in error_events[0]["data"]

    async def test_unknown_module_produces_error(self):
        from services.module_dispatcher import dispatch_modules

        state = _make_minimal_state()

        events = []
        async for evt in dispatch_modules("test-proj-001", state, ["nonexistent"]):
            events.append(evt)

        error_events = [e for e in events if e["event"] == "module_error"]
        assert len(error_events) == 1

        import json
        error_data = json.loads(error_events[0]["data"])
        assert "未知" in error_data.get("error", "") or "Unknown" in error_data.get("error", "")

    async def test_dispatch_continues_after_unknown_module(self):
        from services.module_dispatcher import dispatch_modules

        register_generator(_MockWorkingGen())
        state = _make_minimal_state()

        events = []
        async for evt in dispatch_modules("test-proj-001", state, ["nonexistent", "mock_ok"]):
            events.append(evt)

        import json
        done_events = [e for e in events if e["event"] == "module_done"]
        done_ids = {json.loads(e["data"])["module_id"] for e in done_events}
        assert "mock_ok" in done_ids

    async def test_dispatch_empty_module_list(self):
        from services.module_dispatcher import dispatch_modules

        state = _make_minimal_state()

        events = []
        async for evt in dispatch_modules("test-proj-001", state, []):
            events.append(evt)

        done_events = [e for e in events if e["event"] == "done"]
        assert len(done_events) == 1

        import json
        done_data = json.loads(done_events[0]["data"])
        assert done_data["module_outputs"] == {}


class TestDispatchModulesWithKnowledge:
    """测试 Knowledge Node 前置逻辑。"""

    async def test_uses_existing_knowledge_graph(self):
        from services.module_dispatcher import dispatch_modules

        register_generator(_MockWorkingGen())
        state = _make_minimal_state()

        events = []
        async for evt in dispatch_modules("test-proj-001", state, ["mock_ok"]):
            events.append(evt)

        # 已有 knowledge_graph，不应再调 knowledge_node
        knowledge_events = [e for e in events if e["event"] == "progress"]
        import json
        knowledge_msgs = [
            json.loads(e["data"]).get("phase") for e in knowledge_events
        ]
        # 只有 connecting 和 done，没有 knowledge phase
        assert "knowledge" not in knowledge_msgs

    async def test_triggers_knowledge_node_when_missing(self):
        from services.module_dispatcher import dispatch_modules

        register_generator(_MockWorkingGen())
        state = _make_minimal_state()
        state.pop("knowledge_graph", None)
        state.pop("key_terms", None)

        knowledge_result = {
            "knowledge_graph": {"concepts": [{"id": "c1", "name": "test"}]},
            "key_terms": ["test"],
        }
        with patch(
            "agents.nodes.knowledge_node",
            new=AsyncMock(return_value=knowledge_result),
        ) as mock_knowledge:
            events = []
            async for evt in dispatch_modules("test-proj-001", state, ["mock_ok"]):
                events.append(evt)

        # 应该有一个 knowledge phase 的 progress 事件
        knowledge_events = []
        for e in events:
            if e["event"] == "progress":
                import json
                data = json.loads(e["data"])
                if data.get("phase") == "knowledge":
                    knowledge_events.append(e)
                    break  # 只记录第一个

        mock_knowledge.assert_awaited_once()
        assert knowledge_events


class TestDispatchModulesPersist:
    """测试持久化逻辑（mock DB）。"""

    project_id = "00000000-0000-0000-0000-000000000021"

    async def test_dispatch_persists_on_success(self):
        register_generator(_MockWorkingGen())
        project = MagicMock(dsl_snapshot={})
        session = MagicMock()
        session.get = AsyncMock(return_value=project)
        session.commit = AsyncMock()
        context = MagicMock()
        context.__aenter__ = AsyncMock(return_value=session)
        context.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("db.database.async_session_factory", return_value=context),
            patch("api.versions.save_version", new=AsyncMock()) as save_version,
        ):
            events = [
                event
                async for event in dispatch_modules(
                    self.project_id,
                    _make_minimal_state(project_id=self.project_id),
                    ["mock_ok"],
                )
            ]

        assert project.status == "done"
        assert project.dsl_snapshot["module_outputs"]["mock_ok"]["data"] == "test output"
        save_version.assert_awaited_once()
        session.commit.assert_awaited_once()
        assert events[-1]["event"] == "done"

    async def test_dispatch_handles_persist_failure_gracefully(self, caplog):
        register_generator(_MockWorkingGen())

        with patch(
            "db.database.async_session_factory",
            side_effect=RuntimeError("database unavailable"),
        ):
            events = [
                event
                async for event in dispatch_modules(
                    self.project_id,
                    _make_minimal_state(project_id=self.project_id),
                    ["mock_ok"],
                )
            ]

        assert events[-1]["event"] == "done"
        payload = json.loads(events[-1]["data"])
        assert payload["module_outputs"]["mock_ok"]["data"] == "test output"
        assert "模块产出持久化失败" in caplog.text
