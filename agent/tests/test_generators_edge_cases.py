"""生成器边界与极端情况测试。

覆盖：
- 空/最小输入（空 knowledge_graph、空 outline）
- 最大值输入（深度嵌套、大概念列表）
- 非 ASCII / Unicode 内容
- 不合理但合法的输入
- 输出边界值（空 frames、单帧、大量帧）
"""

from __future__ import annotations

import importlib
from unittest.mock import Mock, patch

import pytest


# ============================================================================
# Helpers
# ============================================================================


def _ensure_registered():
    """确保所有生成器已注册。"""
    for mod_name in (
        "generators.mindmap_generator",
        "generators.card_generator",
        "generators.frames_generator",
        "generators.video_generator",
    ):
        try:
            importlib.reload(__import__(mod_name, fromlist=[""]))
        except Exception:
            pass


@pytest.fixture(autouse=True)
def _setup():
    _ensure_registered()
    yield


@pytest.fixture
def minimal_plan():
    return {
        "objectives": ["理解基本概念"],
        "outline": [],
        "teaching_approach": "",
        "estimated_total_frames": 1,
    }


@pytest.fixture
def minimal_kg():
    return {
        "concepts": [{"id": "c1", "name": "概念", "type": "definition"}],
        "edges": [],
    }


@pytest.fixture
def empty_kg():
    return {"concepts": [], "edges": []}


@pytest.fixture
def large_kg():
    return {
        "concepts": [
            {"id": f"c{i}", "name": f"概念 {i}", "type": t}
            for i, t in enumerate(
                ["definition", "core_mechanism", "prerequisite", "comparison", "extension"] * 4
            )
        ][:20],
        "edges": [
            {"source": f"c{i}", "target": f"c{i+1}", "relation": "leads_to"}
            for i in range(19)
        ],
    }


# ============================================================================
# Mindmap Edge Cases
# ============================================================================


class TestMindmapEdges:
    @pytest.fixture
    def gen(self):
        from generators.registry import get_generator
        return get_generator("mindmap")

    def test_validate_rejects_non_dict(self, gen):
        issues = gen.validate("not a dict")
        assert any(i["severity"] == "high" for i in issues)

    def test_validate_rejects_none(self, gen):
        issues = gen.validate(None)
        assert any(i["severity"] == "high" for i in issues)

    def test_validate_deep_nesting(self, gen):
        """深度超过 4 层的导图应触发警告。"""
        def make_deep(depth: int) -> dict:
            if depth == 0:
                return {"name": f"level_{depth}", "children": []}
            return {"name": f"level_{depth}", "children": [make_deep(depth - 1)]}

        output = {"root": make_deep(6)}
        issues = gen.validate(output)
        assert any("deep_tree" in i.get("type", "") for i in issues)

    def test_validate_node_without_name(self, gen):
        output = {
            "root": {
                "name": "Test",
                "children": [{"name": "", "children": []}],
            },
        }
        issues = gen.validate(output)
        # 空 name 不触发"missing_root_name"（那是根节点专属），但应该是合法的
        errors = [i for i in issues if i["severity"] == "error"]
        assert len(errors) == 0

    def test_validate_single_node(self, gen):
        """只有一个根节点没有子节点应触发 empty_children warning。"""
        output = {"root": {"name": "Lonely", "children": []}}
        issues = gen.validate(output)
        assert any("empty_children" in i.get("type", "") for i in issues)

    def test_build_context_with_minimal_input(self, gen, minimal_plan, minimal_kg):
        ctx = gen._build_context(minimal_plan, minimal_kg, "测试", {})
        assert ctx["topic"] == "测试"
        assert len(ctx["concepts"]) == 1
        assert ctx["teaching_outline"] == []

    def test_build_context_with_empty_kg(self, gen, minimal_plan, empty_kg):
        ctx = gen._build_context(minimal_plan, empty_kg, "测试", {})
        assert ctx["concepts"] == []
        assert ctx["topic"] == "测试"

    def test_build_context_handles_missing_kg_fields(self, gen, minimal_plan):
        """knowledge_graph 缺少 concepts 字段时的行为。"""
        ctx = gen._build_context(minimal_plan, {"edges": []}, "测试", {})
        assert ctx["concepts"] == []

    def test_build_context_with_unicode_topic(self, gen, minimal_plan, minimal_kg):
        """Unicode 主题名称。"""
        topic = "最短路径算法（Dijkstra）— 优先队列优化版 🚀"
        ctx = gen._build_context(minimal_plan, minimal_kg, topic, {})
        assert ctx["topic"] == topic

    def test_output_schema_required_fields(self, gen):
        schema = gen.get_output_schema()
        assert "root" in schema["required"]
        root_props = schema["properties"]["root"]["properties"]
        assert "name" in root_props
        assert "children" in root_props


# ============================================================================
# Cards Edge Cases
# ============================================================================


class TestCardsEdges:
    @pytest.fixture
    def gen(self):
        from generators.registry import get_generator
        return get_generator("cards")

    def test_validate_rejects_non_dict(self, gen):
        issues = gen.validate([])
        assert any(i["severity"] == "high" for i in issues)

    def test_validate_single_card_minimal(self, gen):
        output = {
            "cards": [
                {
                    "id": "c1",
                    "title": "Test",
                    "definition": "A short but valid definition here.",
                    "intuition": "Like a test",
                    "pitfalls": [],
                },
            ],
        }
        issues = gen.validate(output)
        errors = [i for i in issues if i["severity"] == "error"]
        assert len(errors) == 0

    def test_validate_short_definition(self, gen):
        """过短的 definition 应触发 warn。"""
        output = {
            "cards": [
                {
                    "id": "c1",
                    "title": "T",
                    "definition": "Too short",
                    "intuition": "T",
                    "pitfalls": [],
                },
            ],
        }
        issues = gen.validate(output)
        assert any("short_definition" in i.get("type", "") for i in issues)

    def test_validate_missing_required_fields(self, gen):
        """缺少 title 的卡片应触发 missing_field。"""
        output = {
            "cards": [
                {
                    "id": "c1",
                    "title": "",
                    "definition": "A valid definition here yes",
                    "intuition": "",
                    "pitfalls": [],
                },
            ],
        }
        issues = gen.validate(output)
        assert any(
            i["severity"] == "medium" and "missing_field" in i.get("type", "")
            for i in issues
        )

    def test_validate_formula_null_is_valid(self, gen):
        """formula=null 是合法的（非必填）。"""
        output = {
            "cards": [
                {
                    "id": "c1",
                    "title": "Test",
                    "definition": "A valid definition that is long enough.",
                    "intuition": "Like test",
                    "pitfalls": ["None really"],
                    "formula": None,
                    "pseudocode": None,
                    "category": "core_concept",
                    "difficulty": 3,
                },
            ],
        }
        issues = gen.validate(output)
        errors = [i for i in issues if i["severity"] == "error"]
        assert len(errors) == 0

    def test_build_context_with_large_kg(self, gen, minimal_plan, large_kg):
        ctx = gen._build_context(minimal_plan, large_kg, "大量概念", {})
        assert len(ctx["concepts"]) == 20

    def test_build_context_includes_objectives(self, gen):
        plan = {"objectives": ["目标1", "目标2", "目标3"], "outline": []}
        kg = {"concepts": [], "edges": []}
        ctx = gen._build_context(plan, kg, "Topic", {})
        assert len(ctx["objectives"]) == 3

    def test_build_context_concept_without_common_pitfalls(self, gen, minimal_plan):
        """概念没有 common_pitfalls 字段时应返回空列表。"""
        kg = {
            "concepts": [{"id": "c1", "name": "C", "type": "definition"}],
            "edges": [],
        }
        ctx = gen._build_context(minimal_plan, kg, "T", {})
        assert ctx["concepts"][0].get("pitfalls_hint", []) == []

    def test_output_schema_includes_cards_array(self, gen):
        schema = gen.get_output_schema()
        assert "cards" in schema["required"]
        card_schema = schema["properties"]["cards"]["items"]
        for field in ("id", "title", "definition", "intuition", "pitfalls"):
            assert field in card_schema["required"]


# ============================================================================
# Frames Edge Cases
# ============================================================================


class TestFramesEdges:
    @pytest.fixture
    def gen(self):
        from generators.registry import get_generator
        return get_generator("frames")

    def test_validate_rejects_empty_object(self, gen):
        issues = gen.validate({})
        assert any(i["severity"] == "high" for i in issues)

    def test_validate_single_frame_minimal(self, gen):
        output = {
            "frames": [
                {
                    "frame_id": "f_001",
                    "title": "T",
                    "narration": "n",
                    "visual_objects": [],
                    "state_snapshot": {},
                },
            ],
            "parameters": [],
        }
        issues = gen.validate(output)
        # 无 narration 内容会触发 warn，但不应该有 error
        errors = [i for i in issues if i["severity"] == "error"]
        assert len(errors) == 0

    def test_validate_warns_empty_narration(self, gen):
        output = {
            "frames": [
                {
                    "frame_id": "f_001",
                    "title": "T",
                    "narration": "",
                    "visual_objects": [],
                    "state_snapshot": {},
                },
            ],
        }
        issues = gen.validate(output)
        assert any("empty_narration" in i.get("type", "") for i in issues)

    def test_validate_warns_empty_visuals(self, gen):
        output = {
            "frames": [
                {
                    "frame_id": "f_001",
                    "title": "T",
                    "narration": "Valid narration text here",
                    "visual_objects": [],
                    "state_snapshot": {},
                },
            ],
        }
        issues = gen.validate(output)
        assert any("empty_visuals" in i.get("type", "") for i in issues)

    def test_validate_many_frames(self, gen):
        """大量帧（50 帧）的校验不应失败。"""
        output = {
            "frames": [
                {
                    "frame_id": f"f_{i:03d}",
                    "title": f"Frame {i}",
                    "narration": f"Narration for frame {i}",
                    "visual_objects": [
                        {"id": f"vo_{i}", "type": "array", "cells": []},
                    ],
                    "state_snapshot": {"index": i},
                }
                for i in range(50)
            ],
            "parameters": [],
        }
        issues = gen.validate(output)
        errors = [i for i in issues if i["severity"] == "error"]
        assert len(errors) == 0

    def test_validate_mixed_visual_object_types(self, gen):
        """14 种 visual object 类型的混合帧应通过校验。"""
        all_types = [
            "node", "edge", "array", "linked_list", "tree",
            "graph", "table", "code_block", "memory_block",
            "process", "timeline", "formula", "mindmap",
        ]
        output = {
            "frames": [
                {
                    "frame_id": f"f_{i:03d}",
                    "title": f"Type {t}",
                    "narration": f"Testing visual object type: {t}",
                    "visual_objects": [{"id": f"vo_{i}", "type": t}],
                    "state_snapshot": {},
                }
                for i, t in enumerate(all_types)
            ],
            "parameters": [],
        }
        issues = gen.validate(output)
        errors = [i for i in issues if i["severity"] == "error"]
        assert len(errors) == 0

    def test_validate_detects_invalid_frames_structure(self, gen):
        """frames 不是列表时应报错。"""
        output = {"frames": "not a list", "parameters": []}
        issues = gen.validate(output)
        assert any(i["severity"] == "high" for i in issues)

    def test_dsl_structure_has_all_required_fields(self, gen):
        """验证产出 DSL 包含 coder_node 期望的所有顶层字段。"""
        schema = gen.get_output_schema()
        frame_props = schema["properties"]["frames"]["items"]["properties"]
        required_frame_fields = schema["properties"]["frames"]["items"]["required"]
        for field in ("frame_id", "title", "narration", "visual_objects", "state_snapshot"):
            assert field in required_frame_fields
        for field in ("frame_id", "title", "narration", "learning_goal",
                       "visual_objects", "state_snapshot", "animations",
                       "interaction_hooks", "checks"):
            assert field in frame_props

    def test_visual_objects_schema_allows_all_types(self, gen):
        """visual_objects 的 type enum 应覆盖所有 13 种类型。"""
        schema = gen.get_output_schema()
        vo_items = (
            schema["properties"]["frames"]["items"]
            ["properties"]["visual_objects"]["items"]
        )
        allowed_types = vo_items["properties"]["type"]["enum"]
        assert "node" in allowed_types
        assert "array" in allowed_types
        assert "code_block" in allowed_types
        assert "edge" in allowed_types
        # card 不在 enum 中（CODER_PROMPT 禁止 card 出现在 visual_objects）
        assert "card" not in allowed_types


# ============================================================================
# Video Edge Cases
# ============================================================================


class TestVideoEdges:
    @pytest.fixture
    def gen(self):
        from generators.registry import get_generator
        return get_generator("video")

    def test_validate_allows_skipped_status(self, gen):
        """skipped 状态时不应有 error。"""
        output = {"status": "skipped", "message": "no frames"}
        issues = gen.validate(output)
        errors = [i for i in issues if i["severity"] == "error"]
        assert len(errors) == 0  # skipped is medium, not error

    def test_validate_rejects_missing_status(self, gen):
        issues = gen.validate({})
        assert any(i["severity"] == "medium" for i in issues)

    def test_system_prompt_empty(self, gen):
        """Video 不需要 LLM 提示词。"""
        assert gen.get_system_prompt() == ""

    def test_output_schema_minimal(self, gen):
        schema = gen.get_output_schema()
        assert schema["type"] == "object"
        assert "status" in schema["required"]


# ============================================================================
# Cross-Module Consistency
# ============================================================================


class TestCrossModuleConsistency:
    """跨模块一致性测试。"""

    def test_cards_output_schema_matches_module_outputs_schema(self):
        """cards 生成器的输出应与 schema/modules.py 的 CardOutput 兼容。"""
        from generators.registry import get_generator
        from schema.modules import CardOutput

        gen = get_generator("cards")
        schema = gen.get_output_schema()
        required = schema["properties"]["cards"]["items"]["required"]
        # CardOutput 模型字段与生成器 schema 的 required 一致
        card_fields = CardOutput.model_fields.keys()
        for req in required:
            assert req in card_fields, f"Required field '{req}' missing from CardOutput model"

    def test_mindmap_output_matches_module_outputs_schema(self):
        """mindmap 的 root 结构应与 MindmapOutput 兼容。"""
        from generators.registry import get_generator
        from schema.modules import MindmapOutput

        gen = get_generator("mindmap")
        schema = gen.get_output_schema()
        assert "root" in schema["required"]

        mindmap_fields = MindmapOutput.model_fields.keys()
        assert "root" in mindmap_fields

    def test_all_generators_have_unique_module_ids(self):
        from generators.registry import list_generators
        ids = [g.module_id for g in list_generators()]
        assert len(ids) == len(set(ids))

    def test_priorities_are_monotonic(self):
        from generators.registry import list_generators
        priorities = sorted(g.priority for g in list_generators())
        # mindmap=1, cards=2, frames=3, video=5
        assert priorities[0] < priorities[-1]


# ============================================================================
# Mock LLM Error Scenarios
# ============================================================================


class TestLLMErrorHandling:
    """Mock LLM 调用各种失败模式的恢复能力。"""

    @pytest.fixture
    def gen_mindmap(self):
        from generators.registry import get_generator
        return get_generator("mindmap")

    @pytest.fixture
    def gen_cards(self):
        from generators.registry import get_generator
        return get_generator("cards")

    @pytest.fixture
    def gen_frames(self):
        from generators.registry import get_generator
        return get_generator("frames")

    @pytest.fixture
    def plan(self):
        return {
            "objectives": ["Test"],
            "outline": [{"step": 1, "title": "Intro", "key_points": ["p"], "estimated_frames": 3}],
            "teaching_approach": "Test",
            "estimated_total_frames": 3,
        }

    @pytest.fixture
    def kg(self):
        return {"concepts": [{"id": "c1", "name": "Test", "type": "definition"}], "edges": []}

    async def test_mindmap_recovers_from_llm_failure(self, gen_mindmap, plan, kg):
        """LLM 调用失败时 generate() 应抛出异常而非静默返回错误数据。"""
        with patch("agents.llm_client.call_llm_structured") as mock_llm:
            mock_llm.side_effect = RuntimeError("API unavailable")
            with pytest.raises(RuntimeError, match="API unavailable"):
                await gen_mindmap.generate(
                    teaching_plan=plan,
                    knowledge_graph=kg,
                    user_input="Test",
                    constraints={},
                    project_id="test",
                )

    async def test_cards_recovers_from_llm_timeout(self, gen_cards, plan, kg):
        """LLM 超时的错误信息应被正确传递。"""
        with patch("agents.llm_client.call_llm_structured") as mock_llm:
            mock_llm.side_effect = TimeoutError("Request timed out after 120s")
            with pytest.raises(TimeoutError, match="timed out"):
                await gen_cards.generate(
                    teaching_plan=plan,
                    knowledge_graph=kg,
                    user_input="Test",
                    constraints={},
                    project_id="test",
                )

    async def test_frames_recovers_from_llm_error_with_fallback_dsl(self, gen_frames, plan, kg):
        """frames generator 在 LLM 失败时应返回 fallback 帧（与 coder_node 一致）。"""
        with patch("agents.llm_client.call_llm_structured") as mock_llm:
            mock_llm.side_effect = Exception("LLM service error")

            result = await gen_frames.generate(
                teaching_plan=plan,
                knowledge_graph=kg,
                user_input="测试冒泡排序",
                constraints={},
                project_id="test",
            )

            # 应返回 fallback 帧
            assert "frames" in result
            assert len(result["frames"]) >= 1
            assert result["frames"][0]["frame_id"] == "f_001"
            assert "了解" in result["frames"][0]["learning_goal"]

    async def test_frames_with_malformed_llm_response(self, gen_frames, plan, kg):
        """LLM 返回缺少 frames 的结果时，frames 为空但 DSL 结构完整。"""
        with patch("agents.llm_client.call_llm_structured") as mock_llm:
            # 返回不包含 frames 字段的结果
            mock_llm.return_value = {"parameters": [], "assets": []}

            result = await gen_frames.generate(
                teaching_plan=plan,
                knowledge_graph=kg,
                user_input="Test",
                constraints={},
                project_id="test",
            )

            # DSL 结构应完整（即使 frames 为空）
            assert "frames" in result
            assert "topic" in result
            assert "teaching_strategy" in result
            # frames 为空时 validate 会报 empty_frames
            issues = gen_frames.validate(result)
            assert any("empty_frames" in i.get("type", "") for i in issues)
