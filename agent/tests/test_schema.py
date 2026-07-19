"""DSL Schema 单元测试。

用需求文档中的 Dijkstra 样例 JSON 验证 Pydantic 模型的校验能力。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from schema.dsl import (
    AnimationType,
    Frame,
    NodeObject,
    RenderScript,
    VisualObjectType,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def dijkstra_dsl_dict() -> dict:
    """Dijkstra 最短路径算法的完整 DSL JSON。"""
    return {
        "project_id": "proj_001",
        "topic": "Dijkstra Algorithm",
        "audience": "undergraduate_cs",
        "difficulty": "intermediate",
        "teaching_strategy": {
            "objectives": ["理解最短路径概念", "掌握 Dijkstra 算法贪心策略"],
            "prerequisites": ["图的邻接表表示", "贪心算法基本思想"],
            "approach": "先直观演示图遍历 → 引入距离表 → 逐步松弛 → 伪代码对照 → 复杂度分析",
        },
        "knowledge_graph": {
            "concepts": [
                {"id": "c1", "name": "最短路径", "type": "definition"},
                {"id": "c2", "name": "松弛操作", "type": "core_mechanism"},
            ],
            "edges": [
                {"source": "c1", "target": "c2", "relation": "leads_to"},
            ],
        },
        "parameters": [
            {
                "key": "graph_data",
                "label": "图结构",
                "param_type": "graph",
                "default_value": {"nodes": 6},
                "constraints": {"max_nodes": 10, "allow_negative_weights": False},
                "recompute_scope": "all_frames",
            },
        ],
        "frames": [
            {
                "frame_id": "f_001",
                "title": "初始化距离表",
                "learning_goal": "理解初始距离表",
                "narration": "将源节点距离设为 0，其余设为无穷大。",
                "visual_objects": [
                    {
                        "id": "node_a",
                        "type": "node",
                        "label": "A",
                        "position": {"x": 100, "y": 200},
                        "style": {"color": "#4A90D9", "size": 40},
                    },
                    {
                        "id": "node_b",
                        "type": "node",
                        "label": "B",
                        "position": {"x": 300, "y": 100},
                        "style": {"color": "#cccccc", "size": 40},
                    },
                    {
                        "id": "edge_ab",
                        "type": "edge",
                        "label": "4",
                        "source": "node_a",
                        "target": "node_b",
                        "style": {"color": "#888888", "width": 2},
                    },
                    {
                        "id": "dist_table",
                        "type": "table",
                        "label": "距离表",
                        "position": {"x": 500, "y": 50},
                        "headers": ["节点", "距离", "前驱"],
                        "rows": [
                            ["A", 0, "-"],
                            ["B", 99, "-"],
                            ["C", 99, "-"],
                        ],
                    },
                ],
                "state_snapshot": {
                    "distance_table": {"A": 0, "B": 99, "C": 99},
                    "current_node": "A",
                    "visited": ["A"],
                },
                "animations": [
                    {
                        "type": "highlight",
                        "target": "node_a",
                        "duration_ms": 500,
                        "color": "#FFD700",
                    },
                    {
                        "type": "appear",
                        "target": "node_a",
                        "duration_ms": 300,
                    },
                ],
                "interaction_hooks": [],
                "checks": [],
            },
            {
                "frame_id": "f_005",
                "title": "松弛边 (B, C)",
                "learning_goal": "理解松弛操作如何更新距离估计",
                "narration": "当前在节点 B，检查边 (B,C) 权重为 5。dist[B]=4 + 5 = 9 < dist[C]=12，更新 C 的距离为 9。",
                "visual_objects": [
                    {
                        "id": "node_b",
                        "type": "node",
                        "label": "B",
                        "position": {"x": 200, "y": 150},
                        "style": {"color": "#FFD700", "size": 40},
                    },
                    {
                        "id": "edge_bc",
                        "type": "edge",
                        "source": "node_b",
                        "target": "node_c",
                        "label": "5",
                        "style": {"color": "#FF6B6B", "width": 3},
                    },
                ],
                "state_snapshot": {
                    "distance_table": {"A": 0, "B": 4, "C": 9, "D": 99, "E": 99, "F": 99},
                    "current_node": "B",
                    "visited": ["A"],
                },
                "animations": [
                    {"type": "highlight", "target": "node_b", "duration_ms": 500},
                    {"type": "update_value", "target": "distance_c", "from_value": 12, "to_value": 9},
                ],
                "interaction_hooks": [],
                "checks": [
                    {
                        "type": "distance_consistency",
                        "rule": "dist[B] + w(B,C) >= dist[C]",
                    },
                ],
            },
        ],
        "assets": [],
        "export_targets": ["web", "manim_video"],
    }


# ============================================================================
# 校验测试
# ============================================================================


class TestRenderScriptValidation:
    """RenderScript 顶层校验。"""

    def test_parse_dijkstra_dsl(self, dijkstra_dsl_dict: dict) -> None:
        """Dijkstra 完整 DSL 应能通过 Pydantic 校验。"""
        dsl = RenderScript.model_validate(dijkstra_dsl_dict)
        assert dsl.project_id == "proj_001"
        assert dsl.topic == "Dijkstra Algorithm"
        assert dsl.audience == "undergraduate_cs"
        assert dsl.difficulty == "intermediate"

    def test_teaching_strategy(self, dijkstra_dsl_dict: dict) -> None:
        """教学策略应正确解析。"""
        dsl = RenderScript.model_validate(dijkstra_dsl_dict)
        assert len(dsl.teaching_strategy.objectives) == 2
        assert len(dsl.teaching_strategy.prerequisites) == 2
        assert "直观演示" in dsl.teaching_strategy.approach

    def test_knowledge_graph(self, dijkstra_dsl_dict: dict) -> None:
        """知识图谱应正确解析。"""
        dsl = RenderScript.model_validate(dijkstra_dsl_dict)
        assert len(dsl.knowledge_graph.concepts) == 2
        assert dsl.knowledge_graph.concepts[0].id == "c1"
        assert dsl.knowledge_graph.concepts[0].name == "最短路径"
        assert len(dsl.knowledge_graph.edges) == 1

    def test_parameter_count(self, dijkstra_dsl_dict: dict) -> None:
        """参数列表应正确解析。"""
        dsl = RenderScript.model_validate(dijkstra_dsl_dict)
        assert len(dsl.parameters) == 1
        param = dsl.parameters[0]
        assert param.key == "graph_data"
        assert param.param_type == "graph"
        assert param.recompute_scope == "all_frames"

    def test_frame_count(self, dijkstra_dsl_dict: dict) -> None:
        """帧列表应正确解析。"""
        dsl = RenderScript.model_validate(dijkstra_dsl_dict)
        assert len(dsl.frames) == 2


class TestFrameValidation:
    """Frame 层级校验。"""

    @pytest.fixture
    def frame_init(self, dijkstra_dsl_dict: dict) -> dict:
        return dijkstra_dsl_dict["frames"][0]

    @pytest.fixture
    def frame_relax(self, dijkstra_dsl_dict: dict) -> dict:
        return dijkstra_dsl_dict["frames"][1]

    def test_frame_required_fields(self, frame_init: dict) -> None:
        """帧必须包含 frame_id 和 title。"""
        frame = Frame.model_validate(frame_init)
        assert frame.frame_id == "f_001"
        assert frame.title == "初始化距离表"

    def test_frame_narration(self, frame_relax: dict) -> None:
        """讲解文本应正确解析。"""
        frame = Frame.model_validate(frame_relax)
        assert "dist[B]" in frame.narration
        assert "dist[C]" in frame.narration

    def test_frame_state_snapshot(self, frame_relax: dict) -> None:
        """状态快照应正确解析。"""
        frame = Frame.model_validate(frame_relax)
        assert frame.state_snapshot["distance_table"]["A"] == 0
        assert frame.state_snapshot["current_node"] == "B"

    def test_frame_checks(self, frame_relax: dict) -> None:
        """校验规则应正确解析。"""
        frame = Frame.model_validate(frame_relax)
        assert len(frame.checks) == 1
        assert frame.checks[0].type == "distance_consistency"


class TestVisualObjectDiscrimination:
    """VisualObject discriminated union 测试。"""

    def test_node_object(self, dijkstra_dsl_dict: dict) -> None:
        """节点对象应解析为 NodeObject。"""
        dsl = RenderScript.model_validate(dijkstra_dsl_dict)
        vo = dsl.frames[0].visual_objects[0]
        assert vo.type == VisualObjectType.NODE
        assert isinstance(vo, NodeObject)
        assert vo.label == "A"

    def test_edge_object(self, dijkstra_dsl_dict: dict) -> None:
        """边对象应解析为 EdgeObject。"""
        dsl = RenderScript.model_validate(dijkstra_dsl_dict)
        vo = dsl.frames[0].visual_objects[2]
        assert vo.type == VisualObjectType.EDGE
        assert vo.source == "node_a"
        assert vo.target == "node_b"

    def test_table_object(self, dijkstra_dsl_dict: dict) -> None:
        """表格对象应正确解析。"""
        dsl = RenderScript.model_validate(dijkstra_dsl_dict)
        vo = dsl.frames[0].visual_objects[3]
        assert vo.type == VisualObjectType.TABLE
        assert len(vo.headers) == 3
        assert len(vo.rows) == 3

    def test_discriminated_union_type_mix(self, dijkstra_dsl_dict: dict) -> None:
        """混合类型（node + edge + table）应分别正确解析。"""
        dsl = RenderScript.model_validate(dijkstra_dsl_dict)
        types = [vo.type for vo in dsl.frames[0].visual_objects]
        assert types == ["node", "node", "edge", "table"]


class TestAnimationDiscrimination:
    """Animation discriminated union 测试。"""

    def test_highlight_animation(self, dijkstra_dsl_dict: dict) -> None:
        """高亮动画应正确解析。"""
        dsl = RenderScript.model_validate(dijkstra_dsl_dict)
        anim = dsl.frames[0].animations[0]
        assert anim.type == AnimationType.HIGHLIGHT
        assert anim.target == "node_a"
        assert anim.duration_ms == 500

    def test_appear_animation(self, dijkstra_dsl_dict: dict) -> None:
        """出现动画应正确解析。"""
        dsl = RenderScript.model_validate(dijkstra_dsl_dict)
        anim = dsl.frames[0].animations[1]
        assert anim.type == AnimationType.APPEAR

    def test_update_value_animation(self, dijkstra_dsl_dict: dict) -> None:
        """值更新动画应正确解析。"""
        dsl = RenderScript.model_validate(dijkstra_dsl_dict)
        anim = dsl.frames[1].animations[1]
        assert anim.type == AnimationType.UPDATE_VALUE
        # UpdateValueAnimation 特有字段
        if hasattr(anim, "from_value"):
            assert anim.from_value == 12


class TestSerialization:
    """序列化往返测试。"""

    def test_roundtrip(self, dijkstra_dsl_dict: dict) -> None:
        """parse → dump → re-parse 应保持数据一致性。"""
        dsl = RenderScript.model_validate(dijkstra_dsl_dict)
        dumped = dsl.model_dump(mode="json")
        re_parsed = RenderScript.model_validate(dumped)
        assert re_parsed.project_id == dsl.project_id
        assert len(re_parsed.frames) == len(dsl.frames)

    def test_json_serializable(self, dijkstra_dsl_dict: dict) -> None:
        """model_dump(mode='json') 产出的 JSON 应可被 json.dumps 处理。"""
        dsl = RenderScript.model_validate(dijkstra_dsl_dict)
        json_str = dsl.model_dump_json(indent=2)
        assert isinstance(json_str, str)
        # 能被 json.loads 正常反序列化
        parsed = json.loads(json_str)
        assert parsed["project_id"] == "proj_001"


class TestValidationErrors:
    """校验错误测试。"""

    def test_invalid_frame_type_rejected(self) -> None:
        """非法的 VisualObject type 应被拒绝。"""
        data = {
            "frame_id": "f_001",
            "visual_objects": [
                {
                    "id": "x",
                    "type": "invalid_type_xyz",  # 不存在
                    "position": {"x": 0, "y": 0},
                },
            ],
        }
        with pytest.raises(Exception):
            Frame.model_validate(data)

    def test_missing_required_field(self) -> None:
        """缺少必需字段 frame_id 应被拒绝。"""
        data = {"title": "无 frame_id 的帧"}
        with pytest.raises(Exception):
            Frame.model_validate(data)

    def test_invalid_audience_rejected(self) -> None:
        """非法的 audience 值应被拒绝。"""
        data = {
            "project_id": "p",
            "topic": "test",
            "audience": "invalid_audience_type",
        }
        with pytest.raises(Exception):
            RenderScript.model_validate(data)

    def test_frame_missing_edge_source_rejected(self) -> None:
        """Edge 对象缺少 source 字段应被拒绝。"""
        data = {
            "frame_id": "f_001",
            "visual_objects": [
                {
                    "id": "e1",
                    "type": "edge",
                    "target": "node_b",
                    "position": {"x": 0, "y": 0},
                    # 缺少 source
                },
            ],
        }
        with pytest.raises(Exception):
            Frame.model_validate(data)
