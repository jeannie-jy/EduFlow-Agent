"""Agent 节点单元测试。

覆盖 5 个 Agent 节点：planner, knowledge, coder, quality, reflection。
所有测试使用 Mock LLM，不依赖真实 API 调用。
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import (
    AgentStateFactory,
    DSLFactory,
    MockLLMResponse,
    create_mock_llm_response,
)


# ============================================================================
# Planner Node
# ============================================================================


class TestPlannerNode:
    """Planner Agent 节点测试。"""

    @pytest.mark.asyncio
    async def test_normal_planning(self):
        """正常输入应返回结构化教学计划。"""
        from agents.nodes import planner_node

        plan_output = {
            "target_audience_level": "undergraduate_cs",
            "prerequisites": ["数组基础", "循环"],
            "objectives": ["理解冒泡排序原理", "分析时间复杂度"],
            "outline": [
                {
                    "step": 1,
                    "title": "算法介绍",
                    "key_points": ["概念", "名称由来"],
                    "estimated_frames": 3,
                },
                {
                    "step": 2,
                    "title": "逐步演示",
                    "key_points": ["第一轮", "交换过程"],
                    "estimated_frames": 5,
                },
            ],
            "teaching_approach": "直觉先行 → 逐步演示",
            "difficulty_curve": "beginner_friendly",
            "estimated_total_frames": 8,
            "risk_notes": [],
            "suggested_parameters": [],
        }

        with patch("agents.nodes.call_llm_structured", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = plan_output

            state = AgentStateFactory.minimal()
            result = await planner_node(state)

        assert "teaching_plan" in result
        assert result["teaching_plan"]["objectives"] == ["理解冒泡排序原理", "分析时间复杂度"]
        assert len(result["teaching_plan"]["outline"]) == 2
        assert result["status"] == "planning"

    @pytest.mark.asyncio
    async def test_planning_with_materials(self):
        """带材料输入时应将材料内容包含在上下文中。"""
        from agents.nodes import planner_node
        from agents.prompts import PLANNER_SYSTEM_PROMPT

        plan_output = {
            "objectives": ["理解图算法"],
            "outline": [{"step": 1, "title": "图概述", "key_points": ["定义"], "estimated_frames": 3}],
            "teaching_approach": "概念引入",
            "estimated_total_frames": 3,
        }

        with patch("agents.nodes.call_llm_structured", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = plan_output

            state = AgentStateFactory.minimal()
            state["materials"] = [
                {"filename": "课件.pdf", "content_text": "图论基础：顶点、边、路径..."},
            ]
            await planner_node(state)

        # 验证 user_message 包含材料文本
        call_args = mock_llm.call_args
        user_msg = call_args[1]["user_message"]
        assert "图论基础" in user_msg
        assert "user_materials" in user_msg

    @pytest.mark.asyncio
    async def test_planning_with_constraints(self):
        """带约束条件时应包含约束。"""
        from agents.nodes import planner_node

        plan_output = {
            "objectives": ["理解排序"],
            "outline": [{"step": 1, "title": "概述", "key_points": ["定义"], "estimated_frames": 2}],
            "teaching_approach": "演示",
            "estimated_total_frames": 2,
        }

        with patch("agents.nodes.call_llm_structured", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = plan_output

            state = AgentStateFactory.minimal()
            state["constraints"] = {
                "must_cover": ["时间复杂度"],
                "avoid": ["数学证明"],
                "style": "直观严谨",
            }
            await planner_node(state)

        call_args = mock_llm.call_args
        user_msg = call_args[1]["user_message"]
        assert "teacher_constraints" in user_msg
        assert "must_cover" in user_msg
        assert "时间复杂度" in user_msg

    @pytest.mark.asyncio
    async def test_llm_failure_fallback(self):
        """LLM 调用失败时应返回最小回退计划。"""
        from agents.nodes import planner_node

        with patch("agents.nodes.call_llm_structured", side_effect=RuntimeError("API 不可用")):
            state = AgentStateFactory.minimal()
            state["user_input"] = "讲解 Dijkstra 最短路径算法"
            result = await planner_node(state)

        assert "teaching_plan" in result
        plan = result["teaching_plan"]
        assert len(plan["objectives"]) >= 1
        assert len(plan["outline"]) >= 1
        assert plan["estimated_total_frames"] >= 1
        # 回退计划应包含用户主题
        assert "Dijkstra" in str(plan["objectives"]) or "Dijkstra" in str(plan["outline"])

    @pytest.mark.asyncio
    async def test_planner_uses_correct_prompt(self):
        """应使用 PLANNER_SYSTEM_PROMPT。"""
        from agents.nodes import planner_node
        from agents.prompts import PLANNER_SYSTEM_PROMPT

        plan_output = {
            "objectives": ["理解算法"],
            "outline": [{"step": 1, "title": "概述", "key_points": ["x"], "estimated_frames": 1}],
            "teaching_approach": "演示",
            "estimated_total_frames": 1,
        }

        with patch("agents.nodes.call_llm_structured", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = plan_output
            await planner_node(AgentStateFactory.minimal())

        call_args = mock_llm.call_args
        assert call_args[1]["system_prompt"] == PLANNER_SYSTEM_PROMPT

    @pytest.mark.asyncio
    async def test_planner_temperature_is_low(self):
        """Planner 应使用低 temperature（0.3）以保证确定性。"""
        from agents.nodes import planner_node

        plan_output = {
            "objectives": ["x"],
            "outline": [{"step": 1, "title": "x", "key_points": ["x"], "estimated_frames": 1}],
            "teaching_approach": "x",
            "estimated_total_frames": 1,
        }

        with patch("agents.nodes.call_llm_structured", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = plan_output
            await planner_node(AgentStateFactory.minimal())

        call_args = mock_llm.call_args
        assert call_args[1]["temperature"] == 0.3

    @pytest.mark.asyncio
    async def test_output_schema_has_required_fields(self):
        """Planner 的输出 schema 应包含所有必需字段。"""
        import inspect
        from agents.nodes import planner_node

        source = inspect.getsource(planner_node)
        assert "target_audience_level" in source
        assert "prerequisites" in source
        assert "objectives" in source
        assert "outline" in source
        assert "teaching_approach" in source
        assert "estimated_total_frames" in source
        assert '"required"' in source


# ============================================================================
# Knowledge Node
# ============================================================================


class TestKnowledgeNode:
    """Knowledge Agent 节点测试。"""

    @pytest.mark.asyncio
    async def test_normal_knowledge_extraction(self):
        """正常情况应提取知识图谱。"""
        from agents.nodes import knowledge_node

        kg_output = {
            "concepts": [
                {"id": "c1", "name": "最短路径", "type": "definition", "description": "x", "difficulty": 2},
            ],
            "edges": [
                {"source": "c1", "target": "c2", "relation": "leads_to"},
            ],
            "key_terms": ["最短路径", "松弛"],
        }

        with patch("agents.nodes.call_llm_structured", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = kg_output

            state = AgentStateFactory.with_plan()
            result = await knowledge_node(state)

        assert "knowledge_graph" in result
        assert "key_terms" in result
        kg = result["knowledge_graph"]
        assert len(kg["concepts"]) >= 1
        assert len(kg["edges"]) >= 1
        assert isinstance(result["key_terms"], list)

    @pytest.mark.asyncio
    async def test_llm_failure_fallback(self):
        """LLM 失败时应返回最小知识图谱。"""
        from agents.nodes import knowledge_node

        with patch("agents.nodes.call_llm_structured", side_effect=RuntimeError("API 不可用")):
            state = AgentStateFactory.with_plan()
            state["user_input"] = "测试 AVL 树旋转"
            result = await knowledge_node(state)

        kg = result["knowledge_graph"]
        assert len(kg.get("concepts", [])) >= 1
        assert kg["concepts"][0]["id"] == "c1"

    @pytest.mark.asyncio
    async def test_key_terms_is_list_on_fallback(self):
        """回退时 key_terms 应为空列表而非 None。"""
        from agents.nodes import knowledge_node

        with patch("agents.nodes.call_llm_structured", side_effect=RuntimeError("fail")):
            state = AgentStateFactory.with_plan()
            result = await knowledge_node(state)

        assert isinstance(result.get("key_terms"), list)

    @pytest.mark.asyncio
    async def test_knowledge_uses_correct_prompt(self):
        """应使用 KNOWLEDGE_SYSTEM_PROMPT。"""
        from agents.nodes import knowledge_node
        from agents.prompts import KNOWLEDGE_SYSTEM_PROMPT

        kg_output = {
            "concepts": [{"id": "c1", "name": "test", "type": "definition"}],
            "edges": [],
            "key_terms": [],
        }

        with patch("agents.nodes.call_llm_structured", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = kg_output
            await knowledge_node(AgentStateFactory.with_plan())

        call_args = mock_llm.call_args
        assert call_args[1]["system_prompt"] == KNOWLEDGE_SYSTEM_PROMPT

    @pytest.mark.asyncio
    async def test_knowledge_temperature_is_low(self):
        """Knowledge Agent 应使用低 temperature（0.2）。"""
        from agents.nodes import knowledge_node

        kg_output = {
            "concepts": [{"id": "c1", "name": "test", "type": "definition"}],
            "edges": [],
            "key_terms": [],
        }

        with patch("agents.nodes.call_llm_structured", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = kg_output
            await knowledge_node(AgentStateFactory.with_plan())

        call_args = mock_llm.call_args
        assert call_args[1]["temperature"] == 0.2


# ============================================================================
# Coder Node
# ============================================================================


class TestCoderNode:
    """Coder Agent 节点测试。"""

    @pytest.mark.asyncio
    async def test_normal_dsl_generation(self):
        """正常情况应生成完整 DSL。"""
        from agents.nodes import coder_node

        coder_output = {
            "frames": [
                {
                    "frame_id": "f_001",
                    "title": "数组初始化",
                    "learning_goal": "了解初始状态",
                    "narration": "这是一个未排序的数组。",
                    "visual_objects": [
                        {
                            "id": "arr",
                            "type": "array",
                            "label": "数组",
                            "position": {"x": 100, "y": 200},
                            "cells": [{"value": 5}, {"value": 3}],
                        },
                    ],
                    "state_snapshot": {"array": [5, 3]},
                    "animations": [
                        {"type": "appear", "target": "arr", "duration_ms": 500},
                    ],
                    "interaction_hooks": [],
                    "checks": [],
                },
            ],
            "parameters": [],
            "assets": [],
        }

        with patch("agents.nodes.call_llm_structured", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = coder_output

            state = AgentStateFactory.with_knowledge()
            result = await coder_node(state)

        assert "dsl" in result
        dsl = result["dsl"]
        assert len(dsl["frames"]) == 1
        assert dsl["frames"][0]["frame_id"] == "f_001"
        assert dsl["project_id"] == state["project_id"]
        assert "teaching_strategy" in dsl
        assert "knowledge_graph" in dsl
        assert result["status"] == "generating"

    @pytest.mark.asyncio
    async def test_dsl_includes_teaching_strategy(self):
        """生成的 DSL 应包含教学策略。"""
        from agents.nodes import coder_node

        coder_output = {
            "frames": [
                {
                    "frame_id": "f_001",
                    "title": "test",
                    "learning_goal": "test",
                    "narration": "test",
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

        with patch("agents.nodes.call_llm_structured", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = coder_output

            state = AgentStateFactory.with_knowledge()
            result = await coder_node(state)

        dsl = result["dsl"]
        assert "teaching_strategy" in dsl
        assert dsl["teaching_strategy"]["objectives"] == state["teaching_plan"]["objectives"]

    @pytest.mark.asyncio
    async def test_llm_failure_fallback(self):
        """LLM 失败时应返回最小 DSL。"""
        from agents.nodes import coder_node

        with patch("agents.nodes.call_llm_structured", side_effect=RuntimeError("API 不可用")):
            state = AgentStateFactory.with_knowledge()
            state["user_input"] = "讲解冒泡排序"
            result = await coder_node(state)

        dsl = result["dsl"]
        assert len(dsl["frames"]) >= 1
        assert dsl["frames"][0]["frame_id"] == "f_001"
        assert "冒泡" in dsl["frames"][0]["narration"] or "冒泡" in dsl["topic"]

    @pytest.mark.asyncio
    async def test_coder_uses_high_max_tokens(self):
        """Coder 应使用高 max_tokens (8192) 以生成完整 DSL。"""
        from agents.nodes import coder_node

        coder_output = {
            "frames": [
                {
                    "frame_id": "f_001",
                    "title": "x",
                    "learning_goal": "x",
                    "narration": "x",
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

        with patch("agents.nodes.call_llm_structured", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = coder_output
            await coder_node(AgentStateFactory.with_knowledge())

        call_args = mock_llm.call_args
        assert call_args[1]["max_tokens"] == 32768  # Coder 输出完整 DSL，需较大 token 限制

    @pytest.mark.asyncio
    async def test_coder_dsl_structure_complete(self):
        """生成的 DSL 应包含所有顶层字段。"""
        from agents.nodes import coder_node

        coder_output = {
            "frames": [
                {
                    "frame_id": "f_001",
                    "title": "test",
                    "learning_goal": "test",
                    "narration": "test",
                    "visual_objects": [],
                    "state_snapshot": {},
                    "animations": [],
                    "interaction_hooks": [],
                    "checks": [],
                },
            ],
            "parameters": [{"key": "speed", "label": "速度", "type": "number"}],
            "assets": [],
        }

        with patch("agents.nodes.call_llm_structured", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = coder_output
            result = await coder_node(AgentStateFactory.with_knowledge())

        dsl = result["dsl"]
        required_top_level = [
            "project_id", "topic", "audience", "difficulty",
            "teaching_strategy", "knowledge_graph",
            "parameters", "frames", "assets", "export_targets",
        ]
        for field in required_top_level:
            assert field in dsl, f"DSL missing top-level field: {field}"


# ============================================================================
# Quality Node
# ============================================================================


class TestQualityNode:
    """Quality Agent 节点测试。"""

    @pytest.mark.asyncio
    async def test_valid_dsl_passes_quality(self):
        """有效的 DSL 应通过质量检查。"""
        from agents.nodes import quality_node

        # Mock LLM 评分：高分
        llm_quality = {
            "scores": {
                "correctness": 0.9,
                "clarity": 0.85,
                "coherence": 0.8,
                "interactivity": 0.7,
                "renderability": 0.95,
                "completeness": 0.85,
            },
            "overall_score": 0.84,
            "issues": [],
            "suggestions": [],
            "is_blocking": False,
        }

        with patch("agents.nodes.call_llm_structured", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = llm_quality

            state = AgentStateFactory.with_dsl()
            result = await quality_node(state)

        report = result["quality_report"]
        assert "scores" in report
        assert "overall_score" in report
        assert "issues" in report
        assert report["overall_score"] > 0.5
        assert result["status"] == "reviewing"

    @pytest.mark.asyncio
    async def test_invalid_dsl_has_schema_errors(self):
        """包含 Schema 错误的 DSL 应标记为 blocking。"""
        from agents.nodes import quality_node

        llm_quality = {
            "scores": {
                "correctness": 0.8, "clarity": 0.8, "coherence": 0.8,
                "interactivity": 0.7, "renderability": 0.8, "completeness": 0.8,
            },
            "overall_score": 0.79,
            "issues": [],
            "suggestions": [],
            "is_blocking": False,
        }

        with patch("agents.nodes.call_llm_structured", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = llm_quality

            state = AgentStateFactory.with_dsl()
            # 篡改 DSL 使其包含不含 frame_id 的帧
            state["dsl"]["frames"].append({
                "title": "缺少 frame_id",
                "narration": "x",
                "visual_objects": [],
                "state_snapshot": {},
                "animations": [],
                "interaction_hooks": [],
                "checks": [],
            })
            result = await quality_node(state)

        report = result["quality_report"]
        assert report["is_blocking"] is True
        assert len(report["issues"]) >= 1

    @pytest.mark.asyncio
    async def test_state_inconsistency_detected(self):
        """帧间状态不一致应被检测到。"""
        from agents.nodes import quality_node

        llm_quality = {
            "scores": {
                "correctness": 0.8, "clarity": 0.8, "coherence": 0.8,
                "interactivity": 0.7, "renderability": 0.8, "completeness": 0.8,
            },
            "overall_score": 0.79,
            "issues": [],
            "suggestions": [],
            "is_blocking": False,
        }

        with patch("agents.nodes.call_llm_structured", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = llm_quality

            state = AgentStateFactory.with_dsl()
            # 制造状态不一致：值从 4 变成 1000001（超过 ∞ 阈值）
            state["dsl"]["frames"][0]["state_snapshot"] = {"table": {"A": 0, "B": 4}}
            state["dsl"]["frames"][1]["state_snapshot"] = {"table": {"A": 0, "B": 1000001}}
            result = await quality_node(state)

        report = result["quality_report"]
        assert report["is_blocking"] is True
        assert any("state_inconsistency" in str(issue) for issue in report["issues"])

    @pytest.mark.asyncio
    async def test_llm_scoring_fails_gracefully(self):
        """LLM 评分失败时仍应返回确定性评分。"""
        from agents.nodes import quality_node

        with patch("agents.nodes.call_llm_structured", side_effect=RuntimeError("LLM 不可用")):
            state = AgentStateFactory.with_dsl()
            result = await quality_node(state)

        report = result["quality_report"]
        # 即使 LLM 失败，确定性校验仍产生评分
        assert "overall_score" in report
        assert "scores" in report
        assert report["overall_score"] >= 0

    @pytest.mark.asyncio
    async def test_overall_score_below_threshold_is_blocking(self):
        """综合评分低于阈值应标记为 blocking。"""
        from agents.nodes import quality_node

        # LLM 给出极低评分
        llm_quality = {
            "scores": {
                "correctness": 0.3, "clarity": 0.3, "coherence": 0.3,
                "interactivity": 0.3, "renderability": 0.3, "completeness": 0.3,
            },
            "overall_score": 0.3,
            "issues": [{"severity": "high", "description": "概念错误严重"}],
            "suggestions": [],
            "is_blocking": True,
        }

        with patch("agents.nodes.call_llm_structured", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = llm_quality

            state = AgentStateFactory.with_dsl()
            result = await quality_node(state)

        report = result["quality_report"]
        assert report["is_blocking"] is True

    @pytest.mark.asyncio
    async def test_empty_frames_skips_llm_scoring(self):
        """空帧列表时跳过 LLM 评分，仅使用确定性评分。"""
        from agents.nodes import quality_node

        state = AgentStateFactory.with_dsl()
        state["dsl"]["frames"] = []

        result = await quality_node(state)

        report = result["quality_report"]
        assert "overall_score" in report
        # 不使用 LLM 时，renderability 基于 schema 评分
        assert report["scores"]["renderability"] >= 0

    @pytest.mark.asyncio
    async def test_six_dimensions_in_scores(self):
        """评分应包含全部 6 个维度。"""
        from agents.nodes import quality_node

        llm_quality = {
            "scores": {
                "correctness": 0.9, "clarity": 0.9, "coherence": 0.9,
                "interactivity": 0.9, "renderability": 0.9, "completeness": 0.9,
            },
            "overall_score": 0.9,
            "issues": [],
            "suggestions": [],
            "is_blocking": False,
        }

        with patch("agents.nodes.call_llm_structured", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = llm_quality
            result = await quality_node(AgentStateFactory.with_dsl())

        scores = result["quality_report"]["scores"]
        expected_dims = ["correctness", "clarity", "coherence", "interactivity", "renderability", "completeness"]
        for dim in expected_dims:
            assert dim in scores, f"Missing dimension: {dim}"
            assert 0 <= scores[dim] <= 1, f"Score {dim} out of range: {scores[dim]}"


# ============================================================================
# Reflection Node
# ============================================================================


class TestReflectionNode:
    """Reflection Agent 节点测试。"""

    @pytest.mark.asyncio
    async def test_normal_reflection(self):
        """正常修订应修改 DSL 帧。"""
        from agents.nodes import reflection_node

        revision_output = {
            "revision_summary": "修正了距离表更新错误",
            "modified_frame_ids": ["f_002"],
            "updated_frames": [
                {
                    "frame_id": "f_002",
                    "title": "修正后的比较",
                    "narration": "修正后的解说",
                    "visual_objects": [],
                    "state_snapshot": {"array": [3, 5, 8, 1]},
                    "animations": [],
                },
            ],
            "inserted_frames": [],
        }

        with patch("agents.nodes.call_llm_structured", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = revision_output

            state = AgentStateFactory.with_quality_report()
            result = await reflection_node(state)

        assert "dsl" in result
        assert result["reflection_count"] == 1  # count 从 0 开始，+1
        assert len(result["revision_history"]) >= 1

    @pytest.mark.asyncio
    async def test_reflection_increments_count(self):
        """修订次数应正确递增。"""
        from agents.nodes import reflection_node

        revision_output = {
            "revision_summary": "修复",
            "modified_frame_ids": [],
            "updated_frames": [],
            "inserted_frames": [],
        }

        with patch("agents.nodes.call_llm_structured", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = revision_output

            state = AgentStateFactory.with_quality_report()
            state["reflection_count"] = 2
            result = await reflection_node(state)

        assert result["reflection_count"] == 3

    @pytest.mark.asyncio
    async def test_reflection_inserts_new_frames(self):
        """修订可插入新帧。"""
        from agents.nodes import reflection_node

        revision_output = {
            "revision_summary": "插入补充帧",
            "modified_frame_ids": [],
            "updated_frames": [],
            "inserted_frames": [
                {
                    "frame_id": "f_001b",
                    "title": "补充说明帧",
                    "narration": "补充说明",
                    "visual_objects": [],
                    "state_snapshot": {},
                    "animations": [],
                },
            ],
        }

        with patch("agents.nodes.call_llm_structured", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = revision_output

            state = AgentStateFactory.with_quality_report()
            original_frame_count = len(state["dsl"]["frames"])
            result = await reflection_node(state)

        new_frame_count = len(result["dsl"]["frames"])
        assert new_frame_count == original_frame_count + 1

    @pytest.mark.asyncio
    async def test_llm_failure_fallback(self):
        """LLM 失败时保持 DSL 不变。"""
        from agents.nodes import reflection_node

        with patch("agents.nodes.call_llm_structured", side_effect=RuntimeError("API 不可用")):
            state = AgentStateFactory.with_quality_report()
            original_dsl = state["dsl"]
            result = await reflection_node(state)

        # 回退：DSL 保持不变
        assert result["dsl"] == original_dsl
        # revision_summary 应表明自动修复失败
        history = result.get("revision_history", [])
        if history:
            assert "失败" in history[0].get("summary", "")

    @pytest.mark.asyncio
    async def test_reflection_revision_history_recorded(self):
        """修订历史应被正确记录。"""
        from agents.nodes import reflection_node

        revision_output = {
            "revision_summary": "修正了 f_002 的距离计算",
            "modified_frame_ids": ["f_002"],
            "updated_frames": [
                {
                    "frame_id": "f_002",
                    "title": "修正",
                    "narration": "修正",
                    "visual_objects": [],
                    "state_snapshot": {},
                    "animations": [],
                },
            ],
            "inserted_frames": [],
        }

        with patch("agents.nodes.call_llm_structured", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = revision_output

            state = AgentStateFactory.with_quality_report()
            state["revision_history"] = [{"round": 1, "summary": "首次修订"}]
            result = await reflection_node(state)

        history = result["revision_history"]
        assert len(history) == 2
        assert history[1]["reflection_round"] == state["reflection_count"] + 1


# ============================================================================
# Graph topology (LangGraph 图结构)
# ============================================================================


class TestGraphTopology:
    """LangGraph 图拓扑结构测试。"""

    def test_graph_builds_without_error(self):
        """图应能成功构建。"""
        from agents.graph import build_graph
        graph = build_graph()
        assert graph is not None

    def test_graph_has_all_five_nodes(self):
        """图应包含全部 5 个 Agent 节点。"""
        from agents.graph import build_graph
        graph = build_graph()
        nodes = graph.get_graph().nodes

        expected = {"planner", "knowledge", "coder", "quality", "reflection"}
        for node in expected:
            assert node in nodes, f"Graph missing node: {node}"

    def test_graph_has_start_node(self):
        """图应包含 __start__ 节点。"""
        from agents.graph import build_graph
        graph = build_graph()
        nodes = graph.get_graph().nodes
        assert "__start__" in nodes

    def test_graph_entry_point_is_planner(self):
        """入口节点应为 planner。"""
        from agents.graph import build_graph
        graph = build_graph()

        edges = graph.get_graph().edges
        # edges 是 Edge 对象列表，有 source/target 属性
        if isinstance(edges, list):
            start_targets = [e.target for e in edges if getattr(e, "source", None) == "__start__"]
        else:
            start_targets = list(edges.get("__start__", set()))
        assert "planner" in start_targets or any("planner" in str(e) for e in start_targets)

    def test_knowledge_to_coder_has_edge(self):
        """Knowledge → Coder 应有直接边。"""
        from agents.graph import build_graph
        graph = build_graph()
        edges = graph.get_graph().edges

        if isinstance(edges, list):
            knowledge_targets = [e.target for e in edges if getattr(e, "source", None) == "knowledge"]
        else:
            knowledge_targets = list(edges.get("knowledge", set()))
        assert "coder" in knowledge_targets or any("coder" in str(e) for e in knowledge_targets)

    def test_coder_to_quality_has_edge(self):
        """Coder → Quality 应有直接边。"""
        from agents.graph import build_graph
        graph = build_graph()
        edges = graph.get_graph().edges

        if isinstance(edges, list):
            coder_targets = [e.target for e in edges if getattr(e, "source", None) == "coder"]
        else:
            coder_targets = list(edges.get("coder", set()))
        assert "quality" in coder_targets or any("quality" in str(e) for e in coder_targets)

    def test_graph_is_singleton(self):
        """get_graph 应返回同一实例。"""
        import agents.graph as graph_module
        # 保存并重置全局单例，避免污染其他测试中通过 get_graph_async 的 patch
        old_graph = graph_module._graph
        graph_module._graph = None
        try:
            from agents.graph import get_graph
            g1 = get_graph()
            g2 = get_graph()
            assert g1 is g2
        finally:
            graph_module._graph = old_graph