from __future__ import annotations

import asyncio

from evals.graders.deterministic import grade_artifact
from evals.models import EvalCase, EvalExpectation
from tools.algorithm_trace_compiler import compile_algorithm_trace
from tools.normalize_dsl import normalize_dsl
from tools.validate_dsl import check_algorithm_invariants, stabilize_algorithm_trace, validate_dsl_schema


def _case(case_id: str, topic: str) -> EvalCase:
    return EvalCase(
        case_id=case_id,
        version="test",
        domain="algorithm",
        difficulty="beginner",
        topic=topic,
        expected=EvalExpectation(
            required_concepts=[],
            forbidden_claims=[],
            min_frames=1,
            max_frames=10,
        ),
        oracle=None,
    )


def _dijkstra_snapshot_graph() -> dict:
    return {
        "project_id": "test-project",
        "topic": "演示 Dijkstra 不可达节点",
        "frames": [
            {
                "frame_id": "f_001",
                "title": "初始化",
                "visual_objects": [],
                "state_snapshot": {
                    "algorithm": "dijkstra",
                    "dist": {"A": 0, "B": "∞", "C": "∞", "D": "∞"},
                    "visited": [],
                    "queue": [],
                    "graph": {
                        "nodes": ["A", "B", "C", "D"],
                        "edges": [
                            "@{from=A; to=B; weight=4}",
                            "@{from=A; to=C; weight=2}",
                            "@{from=C; to=B; weight=1}",
                            "@{from=B; to=D; weight=5}",
                        ],
                    },
                },
            },
        ],
    }


def test_normalize_promotes_explicit_snapshot_graph_edges():
    result = normalize_dsl(_dijkstra_snapshot_graph())
    graph = next(item for item in result["frames"][0]["visual_objects"] if item["type"] == "graph")
    assert graph["graph_role"] == "primary"
    assert graph["edges"][0] == {"source": "A", "target": "B", "weight": 4}


def test_bellman_edge_scan_is_not_a_priority_queue():
    dsl = {
        "project_id": "test-project",
        "topic": "Bellman-Ford 负权边",
        "frames": [{
            "frame_id": "f_001",
            "title": "初始化",
            "visual_objects": [{
                "id": "primary_graph",
                "type": "graph",
                "label": "有向图：s→a(4), a→b(-3)",
            }],
            "state_snapshot": {
                "algorithm": "bellman_ford",
                "dist": {"s": 0, "a": "∞", "b": "∞"},
                "queue": ["s→a(4)", "a→b(-3)"],
                "round": 0,
            },
        }],
    }
    result = normalize_dsl(dsl)
    snapshot = result["frames"][0]["state_snapshot"]
    assert snapshot["queue"] == []
    assert snapshot["edge_scan"] == [
        {"source": "s", "target": "a", "weight": 4},
        {"source": "a", "target": "b", "weight": -3},
    ]
    assert asyncio.run(validate_dsl_schema(result))["valid"] is True


def test_compiler_orders_late_intermediate_frame_and_derives_state():
    dsl = _dijkstra_snapshot_graph()
    frames = dsl["frames"]
    graph = frames[0]["state_snapshot"]["graph"]
    frames.extend([
        {
            "frame_id": "f_004",
            "title": "总结",
            "visual_objects": [],
            "state_snapshot": {
                "algorithm": "dijkstra", "dist": {"A": 0, "B": 3, "C": 2, "D": 8},
                "visited": ["A", "C", "B", "D"], "queue": [], "graph": graph,
            },
        },
        {
            "frame_id": "f_003b",
            "title": "B 出队",
            "visual_objects": [],
            "state_snapshot": {
                "algorithm": "dijkstra", "dist": {"A": 0, "B": 3, "C": 2, "D": 8},
                "visited": ["A", "C", "B", "D"], "queue": [{"vertex": "D", "priority": 8}], "current": "B", "graph": graph,
            },
        },
    ])
    result = compile_algorithm_trace(stabilize_algorithm_trace(normalize_dsl(dsl)))
    assert [frame["frame_id"] for frame in result["frames"]][-2:] == ["f_003b", "f_004"]
    assert result["algorithm_trace_compilation"]["issues"] == []


def test_smoke_style_artifact_passes_all_deterministic_gates():
    artifact = compile_algorithm_trace(stabilize_algorithm_trace(normalize_dsl(_dijkstra_snapshot_graph())))
    result = asyncio.run(grade_artifact(_case("smoke", "演示 Dijkstra 不可达节点"), artifact))
    assert result["passed"] is True
