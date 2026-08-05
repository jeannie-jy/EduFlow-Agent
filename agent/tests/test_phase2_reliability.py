"""阶段 2 可靠性测试。

覆盖 v0.8 修复中的三组正确性保障：
1. manim_llm_adapter 字段白名单 — 图结构数据不再被剥光
2. dispatcher 全失败落库 — project.status 卡死与 module_errors 丢失问题
3. 生成器 validate 畸形输入 — LLM 输出非预期类型不再崩溃
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from generators.registry import clear_registry, register_generator


# ============================================================================
# 1. manim_llm_adapter — visual_objects 字段白名单
# ============================================================================


class TestManimLLMAdapterWhitelist:
    """图结构数据（边/节点/根节点）必须完整传给 LLM。"""

    def _graph_dsl(self) -> dict:
        return {
            "topic": "Dijkstra 最短路径",
            "frames": [
                {
                    "frame_id": "f_001",
                    "title": "初始状态",
                    "narration": "展示图结构",
                    "state_snapshot": {"distances": {"a": 0}},
                    "visual_objects": [
                        {"id": "e1", "type": "edge", "source": "a", "target": "b",
                         "weight": 5, "directed": True},
                        {"id": "g1", "type": "graph",
                         "nodes": [{"id": "a"}, {"id": "b"}],
                         "edges": [{"source": "a", "target": "b", "weight": 5}]},
                        {"id": "m1", "type": "mindmap",
                         "root": {"name": "Dijkstra"}, "children": [{"name": "贪心"}]},
                    ],
                    "animations": [],
                }
            ],
        }

    def test_edge_fields_survive_whitelist(self):
        from adapters.manim_llm_adapter import _build_user_message

        msg = _build_user_message(self._graph_dsl(), None)
        assert '"source": "a"' in msg
        assert '"target": "b"' in msg
        assert '"weight": 5' in msg
        assert '"directed": true' in msg

    def test_graph_and_mindmap_structure_survive(self):
        from adapters.manim_llm_adapter import _build_user_message

        msg = _build_user_message(self._graph_dsl(), None)
        assert '"edges"' in msg
        assert '"nodes"' in msg
        assert '"root"' in msg
        assert '"children"' in msg


# ============================================================================
# 2. dispatcher — 全模块失败落库
# ============================================================================


class _AlwaysFailGen:
    module_id = "always_fail"
    display_name = "Always Fail"
    description = "Always fails"
    icon = "fail"
    category = "visual"
    priority = 1
    version = "1.0.0"

    async def generate(self, **kwargs):
        raise RuntimeError("Simulated failure")

    def validate(self, output):
        return []

    def get_output_schema(self):
        return {"type": "object"}

    def get_system_prompt(self):
        return "Failing."


@pytest.fixture(autouse=True)
def _clean_registry():
    clear_registry()
    yield
    clear_registry()


PROJECT_ID = "00000000-0000-0000-0000-000000000001"  # 合法 UUID（parse_project_id 要求）


def _make_state():
    return {
        "user_input": "Test topic",
        "project_id": PROJECT_ID,
        "teaching_plan": {"objectives": ["o1"], "outline": []},
        "knowledge_graph": {"concepts": [{"id": "c1", "name": "C", "type": "definition"}], "edges": []},
        "constraints": {},
        "status": "generating",
        "reflection_count": 0,
        "revision_history": [],
    }


class TestDispatchFailurePersistence:
    """全模块失败时 project.status 必须落 failed，module_errors 必须落库。"""

    async def test_all_failed_persists_failed_status_and_errors(self):
        from services.module_dispatcher import dispatch_modules

        register_generator(_AlwaysFailGen())

        # mock DB：async_session_factory 返回带 mock project 的 session
        mock_project = MagicMock()
        mock_project.dsl_snapshot = {}
        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=mock_project)
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("db.database.async_session_factory", return_value=mock_cm):
            events = []
            async for evt in dispatch_modules(PROJECT_ID, _make_state(), ["always_fail"]):
                events.append(evt)

        # 状态机：无产出 + 有错误 → failed
        assert mock_project.status == "failed"
        snapshot = mock_project.dsl_snapshot
        assert "module_errors" in snapshot
        assert "always_fail" in snapshot["module_errors"]

        # done 事件携带错误信息
        last = events[-1]
        assert last["event"] == "done"
        import json
        payload = json.loads(last["data"])
        assert payload["module_errors"] is not None

    async def test_success_persists_done_status(self):
        from services.module_dispatcher import dispatch_modules

        class _OkGen:
            module_id = "always_ok"
            display_name = "Always OK"
            description = "OK"
            icon = "ok"
            category = "visual"
            priority = 1
            version = "1.0.0"

            async def generate(self, **kwargs):
                return {"status": "ok"}

            def validate(self, output):
                return []

            def get_output_schema(self):
                return {"type": "object"}

            def get_system_prompt(self):
                return "OK."

        register_generator(_OkGen())

        mock_project = MagicMock()
        mock_project.dsl_snapshot = {}
        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=mock_project)
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("db.database.async_session_factory", return_value=mock_cm):
            async for _ in dispatch_modules(PROJECT_ID, _make_state(), ["always_ok"]):
                pass

        assert mock_project.status == "done"
        assert "module_outputs" in mock_project.dsl_snapshot


# ============================================================================
# 3. 生成器 validate — 畸形 LLM 输出
# ============================================================================


class TestGeneratorValidateMalformed:
    """LLM 返回非 dict 元素/非字符串时，validate 不得抛异常。"""

    @pytest.mark.parametrize("module_id,output,expected_issue_type", [
        ("frames", {
            "frames": [
                "not-a-dict-frame",
                {"frame_id": "f_001", "title": "t", "narration": "n", "visual_objects": []},
            ],
        }, "invalid_frame_object"),
        ("mindmap", {"root": "not-a-dict-root"}, "invalid_root"),
        ("cards", {
            "cards": [
                42,
                {"id": "c1", "title": "t", "definition": "d", "intuition": "i", "pitfalls": []},
            ],
        }, "invalid_card_object"),
        ("comparison", {
            "topic": "对比",
            "algorithms": [
                None,
                {"name": "A", "pros": ["p1", "p2"], "cons": ["c1"], "description": "d"},
            ],
            "dimensions": ["时间复杂度", "空间复杂度"],
            "comparison_table": [],
            "scenario_analysis": "这是一段足够长的场景分析文本，用于通过长度校验。",
        }, "invalid_algo_object"),
        ("interactive_demo", {"code": {"not": "a string"}}, "invalid_code_type"),
    ])
    @pytest.mark.asyncio
    async def test_malformed_input_no_crash(self, module_id, output, expected_issue_type):
        import importlib

        from generators.registry import get_generator

        # autouse fixture 在每个测试前 clear_registry()，
        # 因此需要 reload 模块重新触发 register_generator（模块级 import 有缓存）
        import generators.mindmap_generator
        import generators.card_generator
        import generators.frames_generator
        import generators.comparison_generator
        import generators.interactive_demo_generator

        for mod in (generators.mindmap_generator, generators.card_generator,
                    generators.frames_generator, generators.comparison_generator,
                    generators.interactive_demo_generator):
            importlib.reload(mod)

        gen = get_generator(module_id)
        assert gen is not None, f"generator {module_id} 未注册"

        # 不应抛异常
        issues = gen.validate(output)
        assert any(i.get("type") == expected_issue_type for i in issues), \
            f"期望 issue type={expected_issue_type}，实际: {[i.get('type') for i in issues]}"
