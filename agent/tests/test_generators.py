"""ModuleGenerator 集成测试。

测试 mindmap、cards、frames、video 四个生成器的：
- LLM mock 场景下的正常生成
- 校验逻辑
- 错误处理
- 输出 Schema 合规
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from generators.registry import list_generators


# ============================================================================
# 测试数据
# ============================================================================


@pytest.fixture
def teaching_plan():
    return {
        "target_audience_level": "undergraduate_cs",
        "prerequisites": ["数组", "循环"],
        "objectives": ["理解冒泡排序原理", "掌握时间复杂度分析"],
        "outline": [
            {"step": 1, "title": "算法介绍", "key_points": ["p1"], "estimated_frames": 3},
            {"step": 2, "title": "逐步演示", "key_points": ["p2"], "estimated_frames": 5},
        ],
        "teaching_approach": "直觉先行 → 逐步演示 → 伪代码",
        "difficulty_curve": "beginner_friendly",
        "estimated_total_frames": 8,
        "risk_notes": [],
        "suggested_parameters": [],
    }


@pytest.fixture
def knowledge_graph():
    return {
        "concepts": [
            {
                "id": "c1", "name": "冒泡排序", "type": "definition",
                "description": "通过反复遍历数组比较相邻元素并交换来排序",
                "common_pitfalls": ["时间复杂度较高", "不适合大数据集"],
            },
            {
                "id": "c2", "name": "比较交换", "type": "core_mechanism",
                "description": "比较相邻两个元素，若顺序不对则交换",
                "common_pitfalls": ["交换次数多导致效率低"],
            },
            {
                "id": "c3", "name": "时间复杂度", "type": "comparison",
                "description": "冒泡排序的时间复杂度为 O(n²)",
                "common_pitfalls": ["最好情况也是 O(n²) 除非优化"],
            },
        ],
        "edges": [
            {"source": "c1", "target": "c2", "relation": "leads_to"},
            {"source": "c2", "target": "c3", "relation": "leads_to"},
        ],
    }


@pytest.fixture
def user_input():
    return "讲解冒泡排序算法"


# ============================================================================
# Fixtures: mock LLM
# ============================================================================


@pytest.fixture
def mock_llm_structured():
    """Mock call_llm_structured 返回可配置结果。"""
    with patch("agents.llm_client.call_llm_structured") as mock:
        mock.return_value = {}
        yield mock


@pytest.fixture(autouse=True)
def _ensure_registered():
    """确保生成器已注册（模块首次导入时自动注册）。

    clear_registry() 在 session 级别清空，不在每个测试间清空。
    """
    import importlib
    for mod_name in (
        "generators.mindmap_generator",
        "generators.card_generator",
        "generators.frames_generator",
        "generators.video_generator",
    ):
        try:
            importlib.reload(__import__(mod_name, fromlist=[""]))
        except Exception:
            pass  # 首次导入即注册，reload 失败不影响
    yield


# ============================================================================
# Tests: 注册
# ============================================================================


class TestGeneratorRegistration:
    """验证所有生成器正确注册。"""

    def test_all_four_registered(self):
        gens = list_generators()
        ids = {g.module_id for g in gens}
        assert ids == {"mindmap", "cards", "frames", "video"}

    def test_mindmap_metadata(self):
        from generators.registry import get_generator
        gen = get_generator("mindmap")
        assert gen is not None
        assert gen.display_name == "思维导图"
        assert gen.category == "visual"
        assert gen.priority == 1

    def test_cards_metadata(self):
        from generators.registry import get_generator
        gen = get_generator("cards")
        assert gen is not None
        assert gen.category == "visual"
        assert gen.priority == 2

    def test_frames_metadata(self):
        from generators.registry import get_generator
        gen = get_generator("frames")
        assert gen is not None
        assert gen.category == "interactive"
        assert gen.priority == 3

    def test_video_metadata(self):
        from generators.registry import get_generator
        gen = get_generator("video")
        assert gen is not None
        assert gen.category == "export"
        assert gen.priority == 5

    def test_all_generators_have_output_schema(self):
        for gen in list_generators():
            schema = gen.get_output_schema()
            assert isinstance(schema, dict)
            assert "type" in schema

    def test_all_generators_have_system_prompt(self):
        for gen in list_generators():
            prompt = gen.get_system_prompt()
            # video generator may return empty string (no LLM needed)
            assert isinstance(prompt, str)


# ============================================================================
# Tests: Mindmap Generator
# ============================================================================


class TestMindmapGenerator:
    @pytest.fixture
    def gen(self):
        from generators.registry import get_generator
        return get_generator("mindmap")

    def test_validate_passes_on_valid_output(self, gen):
        output = {
            "root": {
                "name": "冒泡排序",
                "children": [
                    {
                        "name": "核心思想",
                        "type": "core_mechanism",
                        "children": [
                            {"name": "相邻比较", "children": []},
                            {"name": "逐步冒泡", "children": []},
                        ],
                    },
                    {
                        "name": "复杂度分析",
                        "type": "comparison",
                        "children": [
                            {"name": "O(n²)", "children": []},
                        ],
                    },
                ],
            },
            "metadata": {"total_nodes": 6, "max_depth": 3, "concepts_covered": ["核心思想"]},
        }
        issues = gen.validate(output)
        errors = [i for i in issues if i["severity"] == "error"]
        assert len(errors) == 0

    def test_validate_detects_missing_root_name(self, gen):
        output = {
            "root": {"name": "", "children": []},
        }
        issues = gen.validate(output)
        assert any("missing_root_name" in i.get("type", "") for i in issues)

    def test_validate_warns_empty_children(self, gen):
        output = {
            "root": {"name": "Test", "children": []},
        }
        issues = gen.validate(output)
        assert any("empty_children" in i.get("type", "") for i in issues)

    async def test_generate_with_mock_llm(self, gen, mock_llm_structured, teaching_plan, knowledge_graph, user_input):
        mock_llm_structured.return_value = {
            "root": {
                "name": "冒泡排序",
                "children": [
                    {"name": "核心机制", "type": "core_mechanism", "children": [
                        {"name": "比较", "children": []},
                    ]},
                ],
            },
            "metadata": {"total_nodes": 3, "max_depth": 3, "concepts_covered": ["核心机制"]},
        }

        result = await gen.generate(
            teaching_plan=teaching_plan,
            knowledge_graph=knowledge_graph,
            user_input=user_input,
            constraints={},
            project_id="test",
        )

        assert result is not None
        assert "root" in result
        assert result["root"]["name"] == "冒泡排序"

    def test_output_schema_is_valid_json_schema(self, gen):
        schema = gen.get_output_schema()
        assert schema["type"] == "object"
        assert "root" in schema["required"]

    def test_build_context_includes_concepts(self, gen, teaching_plan, knowledge_graph, user_input):
        ctx = gen._build_context(teaching_plan, knowledge_graph, user_input, {})
        assert ctx["topic"] == user_input
        assert len(ctx["concepts"]) == 3
        assert ctx["concepts"][0]["name"] == "冒泡排序"


# ============================================================================
# Tests: Cards Generator
# ============================================================================


class TestCardGenerator:
    @pytest.fixture
    def gen(self):
        from generators.registry import get_generator
        return get_generator("cards")

    def test_validate_passes_on_valid_cards(self, gen):
        output = {
            "cards": [
                {
                    "id": "card_bubble",
                    "title": "冒泡排序",
                    "definition": "通过反复遍历数组比较相邻元素并交换来排序的算法",
                    "intuition": "就像气泡从水底浮到水面，大的元素慢慢'浮'到数组末尾",
                    "pitfalls": ["容易与选择排序混淆", "忽略优化版本的最佳情况"],
                    "formula": None,
                    "pseudocode": None,
                    "category": "core_concept",
                    "difficulty": 2,
                },
                {
                    "id": "card_swap",
                    "title": "比较交换",
                    "definition": "比较相邻两个元素，若顺序不对则交换位置",
                    "intuition": "就像排队时两个人比身高，矮的站前面",
                    "pitfalls": ["交换操作有开销"],
                    "formula": None,
                    "pseudocode": "if a[j] > a[j+1]: swap(a[j], a[j+1])",
                    "category": "mechanism",
                    "difficulty": 2,
                },
            ],
        }
        issues = gen.validate(output)
        errors = [i for i in issues if i["severity"] == "error"]
        assert len(errors) == 0

    def test_validate_detects_empty_cards(self, gen):
        output = {"cards": []}
        issues = gen.validate(output)
        assert any("empty_cards" in i.get("type", "") for i in issues)

    def test_validate_detects_missing_definition(self, gen):
        output = {
            "cards": [
                {
                    "id": "c1",
                    "title": "Test",
                    "definition": "",
                    "intuition": "",
                    "pitfalls": [],
                },
            ],
        }
        issues = gen.validate(output)
        assert any(
            "missing_field" in i.get("type", "") or "short_definition" in i.get("type", "")
            for i in issues
        )

    def test_validate_warns_no_pitfalls(self, gen):
        output = {
            "cards": [
                {
                    "id": "c1",
                    "title": "Test",
                    "definition": "A test concept definition that is long enough",
                    "intuition": "Like a test",
                    "pitfalls": [],
                },
            ],
        }
        issues = gen.validate(output)
        assert any("no_pitfalls" in i.get("type", "") for i in issues)

    async def test_generate_with_mock_llm(self, gen, mock_llm_structured, teaching_plan, knowledge_graph, user_input):
        mock_llm_structured.return_value = {
            "cards": [
                {
                    "id": "card_bubble",
                    "title": "冒泡排序",
                    "definition": "通过反复遍历数组比较相邻元素并交换来排序",
                    "intuition": "大的元素慢慢浮到末尾",
                    "pitfalls": ["容易混淆"],
                    "formula": None,
                    "pseudocode": None,
                    "category": "core_concept",
                    "difficulty": 2,
                },
            ],
        }

        result = await gen.generate(
            teaching_plan=teaching_plan,
            knowledge_graph=knowledge_graph,
            user_input=user_input,
            constraints={},
            project_id="test",
        )

        assert "cards" in result
        assert len(result["cards"]) == 1
        assert result["cards"][0]["title"] == "冒泡排序"

    def test_output_schema_requires_cards(self, gen):
        schema = gen.get_output_schema()
        assert "cards" in schema["required"]


# ============================================================================
# Tests: Frames Generator
# ============================================================================


class TestFramesGenerator:
    @pytest.fixture
    def gen(self):
        from generators.registry import get_generator
        return get_generator("frames")

    def test_validate_passes_on_valid_frames(self, gen):
        output = {
            "frames": [
                {
                    "frame_id": "f_001",
                    "title": "数组初始化",
                    "learning_goal": "了解初始数组",
                    "narration": "这是一个未排序的数组 [5, 3, 8, 1]。",
                    "visual_objects": [
                        {
                            "id": "arr_display",
                            "type": "array",
                            "label": "数组",
                            "cells": [{"value": 5}, {"value": 3}],
                        },
                    ],
                    "state_snapshot": {"array": [5, 3, 8, 1]},
                    "animations": [{"type": "appear", "target": "arr_display", "duration_ms": 500}],
                    "interaction_hooks": [],
                    "checks": [],
                },
            ],
            "parameters": [],
        }
        issues = gen.validate(output)
        errors = [i for i in issues if i["severity"] == "error"]
        assert len(errors) == 0

    def test_validate_detects_empty_frames(self, gen):
        output = {"frames": [], "parameters": []}
        issues = gen.validate(output)
        assert any("empty_frames" in i.get("type", "") for i in issues)

    def test_validate_detects_duplicate_frame_ids(self, gen):
        output = {
            "frames": [
                {"frame_id": "f_001", "title": "A", "narration": "a", "visual_objects": [], "state_snapshot": {}},
                {"frame_id": "f_001", "title": "B", "narration": "b", "visual_objects": [], "state_snapshot": {}},
            ],
            "parameters": [],
        }
        issues = gen.validate(output)
        assert any("duplicate_frame_ids" in i.get("type", "") for i in issues)

    async def test_generate_with_mock_llm(self, gen, mock_llm_structured, teaching_plan, knowledge_graph, user_input):
        mock_llm_structured.return_value = {
            "frames": [
                {
                    "frame_id": "f_001",
                    "title": "初始状态",
                    "learning_goal": "了解数组",
                    "narration": "初始数组 [5, 3, 8, 1]",
                    "visual_objects": [
                        {"id": "arr", "type": "array", "cells": [{"value": 5}, {"value": 3}]},
                    ],
                    "state_snapshot": {"array": [5, 3, 8, 1]},
                    "animations": [],
                    "interaction_hooks": [],
                    "checks": [],
                },
            ],
            "parameters": [],
            "assets": [],
        }

        result = await gen.generate(
            teaching_plan=teaching_plan,
            knowledge_graph=knowledge_graph,
            user_input=user_input,
            constraints={},
            project_id="test-proj",
        )

        assert "frames" in result
        assert len(result["frames"]) == 1
        assert result["topic"] == user_input
        assert result["project_id"] == "test-proj"

    async def test_dsl_structure_matches_coder_node_format(self, gen, mock_llm_structured, teaching_plan, knowledge_graph, user_input):
        mock_llm_structured.return_value = {
            "frames": [
                {
                    "frame_id": "f_001",
                    "title": "Test",
                    "learning_goal": "test",
                    "narration": "test narration",
                    "visual_objects": [],
                    "state_snapshot": {},
                    "animations": [],
                    "interaction_hooks": [],
                    "checks": [],
                },
            ],
            "parameters": [],
            "assets": [],
        }

        result = await gen.generate(
            teaching_plan=teaching_plan,
            knowledge_graph=knowledge_graph,
            user_input=user_input,
            constraints={},
            project_id="test-proj",
        )

        # 验证 DSL 顶层结构包含 coder_node 的所有字段
        expected_keys = {
            "project_id", "topic", "audience", "difficulty",
            "teaching_strategy", "knowledge_graph", "parameters",
            "frames", "assets", "export_targets",
        }
        assert expected_keys.issubset(set(result.keys()))
        assert result["export_targets"] == ["web", "manim_video"]
        assert "objectives" in result["teaching_strategy"]


# ============================================================================
# Tests: Video Generator
# ============================================================================


class TestVideoGenerator:
    @pytest.fixture
    def gen(self):
        from generators.registry import get_generator
        return get_generator("video")

    def test_metadata(self, gen):
        assert gen.module_id == "video"
        assert gen.category == "export"

    def test_validate_passes_on_queued_status(self, gen):
        output = {
            "status": "queued",
            "job_id": "fake-job-id",
            "config": {"quality": "h"},
            "message": "导出任务已创建",
        }
        issues = gen.validate(output)
        errors = [i for i in issues if i["severity"] == "error"]
        assert len(errors) == 0

    def test_validate_detects_failed_status(self, gen):
        output = {
            "status": "failed",
            "message": "渲染出错",
        }
        issues = gen.validate(output)
        assert any("export_failed" in i.get("type", "") for i in issues)

    def test_validate_detects_skipped_status(self, gen):
        output = {
            "status": "skipped",
            "message": "尚未生成推演帧",
        }
        issues = gen.validate(output)
        assert any("no_frames" in i.get("type", "") for i in issues)

    def test_output_schema(self, gen):
        schema = gen.get_output_schema()
        assert "status" in schema["required"]

    def test_system_prompt_is_empty(self, gen):
        # Video generator doesn't need LLM prompt (delegates to manim_llm_adapter)
        assert gen.get_system_prompt() == ""


# ============================================================================
# Tests: ModuleDispatcher integration
# ============================================================================


class TestDispatcherWithRealGenerators:
    """测试 ModuleDispatcher 与真实生成器的集成。"""

    async def test_dispatcher_runs_registered_generators(self, mock_llm_structured):
        from services.module_dispatcher import dispatch_modules

        # 设置 mock LLM 为每个模块返回合理的结果
        def make_result(*args, **kwargs):
            schema = kwargs.get("output_schema", {})
            if "root" in schema.get("properties", {}):
                return {
                    "root": {"name": "Test", "children": [
                        {"name": "A", "type": "definition", "children": []},
                    ]},
                }
            if "cards" in schema.get("properties", {}):
                return {
                    "cards": [
                        {
                            "id": "c1", "title": "Test", "definition": "A test concept definition here",
                            "intuition": "Like a test", "pitfalls": ["None"],
                            "category": "core_concept", "difficulty": 2,
                        },
                    ],
                }
            if "frames" in schema.get("properties", {}):
                return {
                    "frames": [
                        {
                            "frame_id": "f_001", "title": "Test", "narration": "test",
                            "visual_objects": [], "state_snapshot": {},
                            "animations": [], "interaction_hooks": [], "checks": [],
                        },
                    ],
                    "parameters": [],
                    "assets": [],
                }
            return {}

        mock_llm_structured.side_effect = make_result

        state = {
            "user_input": "Test topic",
            "project_id": "00000000-0000-0000-0000-000000000002",
            "teaching_plan": {
                "objectives": ["Test"],
                "outline": [{"step": 1, "title": "Intro", "key_points": ["p1"], "estimated_frames": 3}],
                "teaching_approach": "Test",
                "estimated_total_frames": 3,
            },
            "knowledge_graph": {
                "concepts": [{"id": "c1", "name": "Test", "type": "definition"}],
                "edges": [],
            },
            "constraints": {},
            "status": "generating",
            "reflection_count": 0,
            "revision_history": [],
        }

        events = []
        async for evt in dispatch_modules("00000000-0000-0000-0000-000000000002", state, ["mindmap"]):
            events.append(evt)

        event_types = {e["event"] for e in events}
        assert "module_start" in event_types
        assert "module_done" in event_types
        assert "done" in event_types

    async def test_dispatcher_runs_multiple_modules(self, mock_llm_structured):
        from services.module_dispatcher import dispatch_modules

        mock_llm_structured.side_effect = lambda **kwargs: (
            {"root": {"name": "T", "children": []}}
            if "root" in kwargs.get("output_schema", {}).get("properties", {})
            else {"cards": [{"id": "c1", "title": "T", "definition": "A test concept definition.", "intuition": "Like T", "pitfalls": ["X"], "category": "core", "difficulty": 1}]}
        )

        state = {
            "user_input": "Test",
            "project_id": "00000000-0000-0000-0000-000000000003",
            "teaching_plan": {
                "objectives": ["Test"],
                "outline": [{"step": 1, "title": "I", "key_points": ["p"], "estimated_frames": 1}],
                "teaching_approach": "T",
                "estimated_total_frames": 1,
            },
            "knowledge_graph": {
                "concepts": [{"id": "c1", "name": "Test", "type": "definition"}],
                "edges": [],
            },
            "constraints": {},
            "status": "generating",
            "reflection_count": 0,
            "revision_history": [],
        }

        events = []
        async for evt in dispatch_modules("00000000-0000-0000-0000-000000000003", state, ["mindmap", "cards"]):
            events.append(evt)

        done_events = [
            e for e in events
            if e["event"] == "module_done" or e["event"] == "done"
        ]
        # 2 module_done + 1 done
        assert len([e for e in done_events if e["event"] == "module_done"]) == 2
        assert any(e["event"] == "done" for e in events)
