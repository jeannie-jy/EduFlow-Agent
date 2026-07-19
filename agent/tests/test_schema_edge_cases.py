"""DSL Schema 边界条件与异常测试。

覆盖 14 种 VisualObject + 16 种 Animation 的全部类型实例化。
测试极端值、空值、类型错误等边界情况。
"""

from __future__ import annotations

import pytest

from schema.dsl import (
    AnimationType,
    AppearAnimation,
    ArrayObject,
    Asset,
    CardObject,
    Check,
    CodeBlockObject,
    CompareAnimation,
    ConceptEdge,
    ConceptNode,
    DequeueAnimation,
    DisappearAnimation,
    EdgeObject,
    EnqueueAnimation,
    FormulaObject,
    Frame,
    GraphObject,
    HighlightAnimation,
    InteractionHook,
    KnowledgeGraph,
    LinkedListObject,
    LockAnimation,
    MemoryBlockObject,
    MergeAnimation,
    MindmapObject,
    MoveAnimation,
    NodeObject,
    Parameter,
    ProcessObject,
    RelaxEdgeAnimation,
    RenderScript,
    ScheduleAnimation,
    SplitAnimation,
    Style,
    SwapAnimation,
    TableObject,
    TeachingStrategy,
    TimelineObject,
    TransformAnimation,
    TreeObject,
    UnlockAnimation,
    UpdateValueAnimation,
    VisualObjectType,
)


# ============================================================================
# VisualObject — 全部 14 种类型实例化
# ============================================================================


class TestAllVisualObjectTypes:
    """每种 VisualObject 类型都能独立实例化并通过校验。"""

    def test_node_object(self):
        vo = NodeObject(id="n1", label="Node 1", node_type="circle")
        assert vo.type == VisualObjectType.NODE
        assert vo.node_type == "circle"

    def test_edge_object(self):
        vo = EdgeObject(id="e1", source="a", target="b", weight=5.0, directed=True)
        assert vo.type == VisualObjectType.EDGE
        assert vo.weight == 5.0

    def test_edge_object_defaults(self):
        vo = EdgeObject(id="e1", source="a", target="b")
        assert vo.directed is True
        assert vo.weight is None

    def test_array_object(self):
        vo = ArrayObject(
            id="arr1",
            cells=[{"value": 5}, {"value": 3}, {"value": 8}],
        )
        assert vo.type == VisualObjectType.ARRAY
        assert len(vo.cells) == 3

    def test_linked_list_object(self):
        vo = LinkedListObject(
            id="ll1",
            nodes=[
                {"id": "n1", "value": 10, "next": "n2"},
                {"id": "n2", "value": 20, "next": None},
            ],
        )
        assert vo.type == VisualObjectType.LINKED_LIST

    def test_tree_object(self):
        vo = TreeObject(
            id="tree1",
            root_id="r1",
            nodes=[
                {"id": "r1", "value": 50, "color": "black"},
                {"id": "l1", "value": 30, "color": "red"},
            ],
        )
        assert vo.type == VisualObjectType.TREE
        assert vo.root_id == "r1"

    def test_graph_object(self):
        vo = GraphObject(
            id="graph1",
            nodes=[{"id": "A"}, {"id": "B"}, {"id": "C"}],
            edges=[
                {"source": "A", "target": "B", "weight": 4},
                {"source": "B", "target": "C", "weight": 5},
            ],
        )
        assert vo.type == VisualObjectType.GRAPH
        assert len(vo.nodes) == 3

    def test_table_object(self):
        vo = TableObject(
            id="t1",
            headers=["节点", "距离", "前驱"],
            rows=[["A", 0, "-"], ["B", 99, "-"], ["C", 99, "-"]],
        )
        assert vo.type == VisualObjectType.TABLE
        assert len(vo.headers) == 3

    def test_code_block_object(self):
        vo = CodeBlockObject(
            id="code1",
            language="python",
            code="def bubble_sort(arr):\n    pass",
            highlight_lines=[1],
        )
        assert vo.type == VisualObjectType.CODE_BLOCK
        assert vo.language == "python"

    def test_memory_block_object(self):
        vo = MemoryBlockObject(
            id="mem1",
            blocks=[{"address": "0x1000", "size": 64, "label": "page_table"}],
        )
        assert vo.type == VisualObjectType.MEMORY_BLOCK

    def test_process_object(self):
        vo = ProcessObject(
            id="proc1",
            pid="P1",
            state="running",
            attributes={"priority": 5, "burst_time": 10},
        )
        assert vo.type == VisualObjectType.PROCESS
        assert vo.pid == "P1"

    def test_timeline_object(self):
        vo = TimelineObject(
            id="tl1",
            events=[
                {"time": 0, "event": "P1 arrives"},
                {"time": 5, "event": "P1 completes"},
            ],
        )
        assert vo.type == VisualObjectType.TIMELINE

    def test_formula_object(self):
        vo = FormulaObject(id="f1", latex=r"E = mc^2")
        assert vo.type == VisualObjectType.FORMULA

    def test_card_object(self):
        vo = CardObject(
            id="card1",
            title="松弛操作",
            content="if dist[u] + w(u,v) < dist[v]: dist[v] = dist[u] + w(u,v)",
        )
        assert vo.type == VisualObjectType.CARD

    def test_mindmap_object(self):
        vo = MindmapObject(
            id="mm1",
            root={"id": "root", "label": "虚拟内存"},
            children=[
                {"id": "c1", "label": "分页"},
                {"id": "c2", "label": "分段"},
            ],
        )
        assert vo.type == VisualObjectType.MINDMAP


# ============================================================================
# Animation — 全部 16 种类型实例化
# ============================================================================


class TestAllAnimationTypes:
    """每种 Animation 类型都能独立实例化。"""

    def test_appear(self):
        a = AppearAnimation(target="node_a", duration_ms=300)
        assert a.type == AnimationType.APPEAR

    def test_disappear(self):
        a = DisappearAnimation(target="node_a", duration_ms=300)
        assert a.type == AnimationType.DISAPPEAR

    def test_highlight(self):
        a = HighlightAnimation(target="node_a", duration_ms=500, color="#FFD700")
        assert a.type == AnimationType.HIGHLIGHT

    def test_transform(self):
        a = TransformAnimation(target="node_a")
        assert a.type == AnimationType.TRANSFORM

    def test_move(self):
        a = MoveAnimation(target="node_a", duration_ms=800)
        assert a.type == AnimationType.MOVE

    def test_update_value(self):
        a = UpdateValueAnimation(target="cell_1", from_value=12, to_value=9)
        assert a.type == AnimationType.UPDATE_VALUE
        assert a.from_value == 12

    def test_compare(self):
        a = CompareAnimation(target="array_1", left="before", right="after")
        assert a.type == AnimationType.COMPARE

    def test_swap(self):
        a = SwapAnimation(target="cell_0", target_2="cell_1")
        assert a.type == AnimationType.SWAP

    def test_relax_edge(self):
        a = RelaxEdgeAnimation(target="edge_ab", new_weight=4.0)
        assert a.type == AnimationType.RELAX_EDGE

    def test_enqueue(self):
        a = EnqueueAnimation(target="queue_1")
        assert a.type == AnimationType.ENQUEUE

    def test_dequeue(self):
        a = DequeueAnimation(target="queue_1")
        assert a.type == AnimationType.DEQUEUE

    def test_split(self):
        a = SplitAnimation(target="node_1")
        assert a.type == AnimationType.SPLIT

    def test_merge(self):
        a = MergeAnimation(target="node_1")
        assert a.type == AnimationType.MERGE

    def test_schedule(self):
        a = ScheduleAnimation(target="cpu_timeline", params={"process": "P2", "start": 5})
        assert a.type == AnimationType.SCHEDULE

    def test_lock(self):
        a = LockAnimation(target="resource_1")
        assert a.type == AnimationType.LOCK

    def test_unlock(self):
        a = UnlockAnimation(target="resource_1")
        assert a.type == AnimationType.UNLOCK


# ============================================================================
# Frame 边界测试
# ============================================================================


class TestFrameEdgeCases:
    """Frame 的边界情况测试。"""

    def test_frame_minimal(self):
        """最小 Frame：只有必需字段。"""
        f = Frame(frame_id="f_min", title="")
        assert f.frame_id == "f_min"
        assert f.narration == ""
        assert f.visual_objects == []
        assert f.state_snapshot == {}

    def test_frame_empty_state_snapshot(self):
        """state_snapshot 为空字典是合法的。"""
        f = Frame(frame_id="f_001", state_snapshot={})
        assert f.state_snapshot == {}

    def test_frame_large_state_snapshot(self):
        """state_snapshot 包含大量数据。"""
        large_state = {f"key_{i}": i for i in range(1000)}
        f = Frame(frame_id="f_001", state_snapshot=large_state)
        assert len(f.state_snapshot) == 1000

    def test_frame_mixed_visual_objects(self):
        """一帧中的 visual_objects 可以混合多种类型。"""
        from schema.dsl import Animation, VisualObject

        f = Frame(
            frame_id="f_001",
            visual_objects=[
                NodeObject(id="n1", label="N", node_type="circle"),
                EdgeObject(id="e1", source="n1", target="n2"),
                TableObject(id="t1", headers=["K", "V"], rows=[]),
                CodeBlockObject(id="c1", language="python", code="x = 1"),
            ],
            animations=[
                HighlightAnimation(target="n1"),
                AppearAnimation(target="t1"),
            ],
        )
        assert len(f.visual_objects) == 4
        types = [vo.type for vo in f.visual_objects]
        assert types == ["node", "edge", "table", "code_block"]

    def test_frame_with_all_interaction_hooks(self):
        """一帧可以有多种交互控件。"""
        f = Frame(
            frame_id="f_interactive",
            interaction_hooks=[
                InteractionHook(type="slider", param="speed", range=[1, 10]),
                InteractionHook(type="select", param="algorithm", options=["FCFS", "SJF", "RR"]),
                InteractionHook(type="switch", param="show_pseudocode"),
                InteractionHook(type="button", param="reset"),
            ],
        )
        assert len(f.interaction_hooks) == 4

    def test_frame_serialization_extra_fields_preserved(self):
        """额外字段应在序列化中保留（ConfigDict extra='allow'）。"""
        f = Frame(
            frame_id="f_001",
            title="Test",
            custom_field="preserved",
            another_extra=123,
        )
        dumped = f.model_dump()
        assert dumped.get("custom_field") == "preserved"
        assert dumped.get("another_extra") == 123


# ============================================================================
# Parameter 边界测试
# ============================================================================


class TestParameterEdgeCases:
    """Parameter 边界情况。"""

    def test_parameter_number(self):
        p = Parameter(
            key="node_count",
            label="节点数量",
            param_type="number",
            default_value=6,
            constraints={"min": 2, "max": 20},
        )
        assert p.key == "node_count"
        assert p.param_type == "number"

    def test_parameter_graph_type(self):
        p = Parameter(
            key="graph_data",
            label="图结构",
            param_type="graph",
            default_value={"nodes": [{"id": "A"}], "edges": []},
            constraints={"max_nodes": 10, "allow_negative_weights": False},
            recompute_scope="all_frames",
        )
        assert p.recompute_scope == "all_frames"

    def test_parameter_local_recompute(self):
        p = Parameter(
            key="speed",
            label="播放速度",
            param_type="number",
            default_value=1.0,
            recompute_scope="local",
        )
        assert p.recompute_scope == "local"

    def test_parameter_visibility_teacher(self):
        p = Parameter(key="advanced", label="高级参数", visibility="teacher")
        assert p.visibility == "teacher"


# ============================================================================
# TeachingStrategy & KnowledgeGraph 测试
# ============================================================================


class TestTeachingStrategy:
    def test_strategy_minimal(self):
        s = TeachingStrategy()
        assert s.objectives == []
        assert s.prerequisites == []
        assert s.approach == ""

    def test_strategy_full(self):
        s = TeachingStrategy(
            objectives=["目标1", "目标2"],
            prerequisites=["前置1"],
            approach="直觉优先 → 逐步细化",
            risk_notes=["注意概念混淆"],
        )
        assert len(s.objectives) == 2


class TestKnowledgeGraph:
    def test_graph_minimal(self):
        kg = KnowledgeGraph()
        assert kg.concepts == []
        assert kg.edges == []

    def test_graph_with_concepts(self):
        kg = KnowledgeGraph(
            concepts=[
                ConceptNode(id="c1", name="最短路径", type="definition"),
                ConceptNode(id="c2", name="松弛操作", type="core_mechanism"),
            ],
            edges=[
                ConceptEdge(source="c1", target="c2", relation="leads_to"),
            ],
        )
        assert len(kg.concepts) == 2
        assert kg.edges[0].relation == "leads_to"


# ============================================================================
# RenderScript 顶层测试
# ============================================================================


class TestRenderScriptEdgeCases:
    """RenderScript 顶层边界测试。"""

    def test_render_script_minimal(self):
        """最小 RenderScript 应能通过校验。"""
        rs = RenderScript(
            project_id="p1",
            topic="Test",
        )
        assert rs.project_id == "p1"
        assert rs.frames == []
        assert rs.parameters == []

    def test_render_script_full(self):
        """使用 Dijkstra 样例数据的完整 RenderScript。"""
        rs = RenderScript(
            project_id="proj_001",
            topic="Dijkstra Algorithm",
            audience="undergraduate_cs",
            difficulty="intermediate",
            teaching_strategy=TeachingStrategy(
                objectives=["理解最短路径"],
                prerequisites=["图的表示"],
                approach="直观演示 → 逐步细化",
            ),
            knowledge_graph=KnowledgeGraph(
                concepts=[ConceptNode(id="c1", name="最短路径", type="definition")],
                edges=[ConceptEdge(source="c1", target="c2", relation="leads_to")],
            ),
            parameters=[
                Parameter(
                    key="graph_data",
                    label="图结构",
                    param_type="graph",
                    default_value={"nodes": 6},
                ),
            ],
            frames=[
                Frame(
                    frame_id="f_001",
                    title="初始化",
                    narration="将源节点距离设为 0...",
                    visual_objects=[
                        NodeObject(id="node_a", label="A", node_type="circle"),
                        NodeObject(id="node_b", label="B"),
                        EdgeObject(id="edge_ab", source="node_a", target="node_b", weight=4),
                    ],
                    state_snapshot={"distance_table": {"A": 0, "B": 99}},
                    animations=[HighlightAnimation(target="node_a"), AppearAnimation(target="node_b")],
                ),
            ],
            assets=[
                Asset(
                    id="card_relax",
                    type="card",
                    title="松弛操作",
                    content={"definition": "...", "example": "..."},
                ),
            ],
            export_targets=["web", "manim_video"],
        )
        assert len(rs.frames) == 1
        assert len(rs.assets) == 1

    def test_render_script_invalid_audience_rejected(self):
        with pytest.raises(Exception):
            RenderScript(project_id="p1", topic="t", audience="invalid_audience")

    def test_render_script_invalid_difficulty_accepted(self):
        """difficulty 在 RenderScript 中是枚举，非法值应被拒绝。"""
        with pytest.raises(Exception):
            RenderScript(project_id="p1", topic="t", difficulty="super_easy")


# ============================================================================
# 序列化往返测试
# ============================================================================


class TestRoundTripSerialization:
    """各种类型的 JSON 往返测试。"""

    def test_node_roundtrip(self):
        vo = NodeObject(id="n1", label="Hello", node_type="circle")
        dumped = vo.model_dump_json()
        reloaded = NodeObject.model_validate_json(dumped)
        assert reloaded.id == "n1"
        assert reloaded.node_type == "circle"

    def test_edge_roundtrip(self):
        vo = EdgeObject(id="e1", source="a", target="b", weight=3.5, directed=False)
        dumped = vo.model_dump_json()
        reloaded = EdgeObject.model_validate_json(dumped)
        assert reloaded.weight == 3.5
        assert reloaded.directed is False

    def test_graph_field_alias(self):
        """GraphObject 的 graph_edges 字段应正确序列化为 'edges'。"""
        vo = GraphObject(
            id="g1",
            nodes=[{"id": "A"}],
            graph_edges=[{"source": "A", "target": "B"}],
        )
        dumped = vo.model_dump(by_alias=True)
        assert "edges" in dumped
        # 使用 alias 后字段名应该是 'edges' 而非 'graph_edges' 或 'edges_list'
        assert dumped.get("edges") == [{"source": "A", "target": "B"}]

    def test_frame_roundtrip(self):
        f = Frame(
            frame_id="f_001",
            title="Test",
            state_snapshot={"value": 42, "nested": {"deep": True}},
        )
        dumped = f.model_dump_json()
        reloaded = Frame.model_validate_json(dumped)
        assert reloaded.state_snapshot["value"] == 42
        assert reloaded.state_snapshot["nested"]["deep"] is True

    def test_null_and_special_values_in_state_snapshot(self):
        """state_snapshot 中的 None/float/大数值应正确序列化。"""
        f = Frame(
            frame_id="f_001",
            state_snapshot={
                "null_val": None,
                "inf_val": float("inf"),
                "neg_inf": float("-inf"),
                "big_num": 10**18,
                "empty_str": "",
                "zero": 0,
                "false_val": False,
            },
        )
        dumped = f.model_dump_json()
        reloaded = Frame.model_validate_json(dumped)
        assert reloaded.state_snapshot["null_val"] is None
        assert reloaded.state_snapshot["zero"] == 0
        assert reloaded.state_snapshot["false_val"] is False


# ============================================================================
# 质量检查工具测试
# ============================================================================


@pytest.mark.asyncio
class TestValidateDSLTool:
    """validate_dsl_schema 和 check_state_consistency 工具测试。"""

    async def test_validate_valid_dsl(self):
        from tools.validate_dsl import validate_dsl_schema

        dsl = {
            "project_id": "p1",
            "topic": "test",
            "frames": [
                {
                    "frame_id": "f_001",
                    "title": "test",
                    "narration": "test",
                    "visual_objects": [],
                    "state_snapshot": {},
                    "animations": [],
                    "interaction_hooks": [],
                    "checks": [],
                },
            ],
        }
        result = await validate_dsl_schema(dsl)
        assert result["valid"] is True
        assert len(result["errors"]) == 0

    async def test_validate_missing_frame_id(self):
        from tools.validate_dsl import validate_dsl_schema

        dsl = {
            "project_id": "p1",
            "topic": "test",
            "frames": [
                {
                    "title": "no frame_id",
                    "narration": "test",
                    "visual_objects": [],
                    "state_snapshot": {},
                    "animations": [],
                    "interaction_hooks": [],
                    "checks": [],
                },
            ],
        }
        result = await validate_dsl_schema(dsl)
        assert result["valid"] is False
        assert any("frame_id" in err for err in result["errors"])

    async def test_check_consistent_frames(self):
        from tools.validate_dsl import check_state_consistency

        frames = [
            {"frame_id": "f_001", "state_snapshot": {"table": {"A": 0, "B": 99}}},
            {"frame_id": "f_002", "state_snapshot": {"table": {"A": 0, "B": 4}}},
        ]
        result = await check_state_consistency(frames)
        assert result["consistent"] is True

    async def test_check_inconsistent_frames(self):
        from tools.validate_dsl import check_state_consistency

        # 模拟：f_001 中 B=4（有效值），f_002 中 B 突然被重置
        # check_state_consistency 的阈值是 >= 1_000_000 视为无穷大
        frames = [
            {"frame_id": "f_001", "state_snapshot": {"table": {"A": 0, "B": 4}}},
            {"frame_id": "f_002", "state_snapshot": {"table": {"A": 0, "B": 1000001}}},
        ]
        result = await check_state_consistency(frames)
        # B 从 4 变成 1000001（超过 ∞ 阈值），应标记为不一致
        assert result["consistent"] is False
        assert len(result["issues"]) >= 1
