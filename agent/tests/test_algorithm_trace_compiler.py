from __future__ import annotations

from tools.algorithm_trace_compiler import compile_algorithm_trace
from tools.normalize_dsl import normalize_dsl


def _dijkstra_dsl() -> dict:
    graph = {
        "id": "primary_graph",
        "type": "graph",
        "graph_role": "primary",
        "nodes": [{"id": "s"}, {"id": "a"}, {"id": "b"}],
        "edges": [
            {"source": "s", "target": "a", "weight": 4},
            {"source": "s", "target": "b", "weight": 1},
            {"source": "b", "target": "a", "weight": 2},
        ],
    }
    return {
        "topic": "Dijkstra 最短路径",
        "frames": [
            {
                "frame_id": "f_001",
                "title": "初始化",
                "visual_objects": [graph],
                "state_snapshot": {"distances": {"s": 0, "a": "∞", "b": "∞"}},
            },
            {
                "frame_id": "f_002",
                "title": "取出 s 并松弛邻边",
                "visual_objects": [graph],
                "state_snapshot": {
                    "current": "s",
                    "dist": {"s": 0, "a": "∞", "b": "∞"},
                    "visited": ["s"],
                    "queue": [["a", 4], ["b", 1]],
                },
            },
            {
                "frame_id": "f_003",
                "title": "取出 b 并松弛",
                "visual_objects": [graph],
                "state_snapshot": {
                    "current": "b",
                    "dist": {"s": 0, "a": 3, "b": 1},
                    "visited": ["s", "b"],
                    "events": [
                        {"operation": "select", "target": "b"},
                        {"operation": "relax", "source": "b", "target": "a", "weight": 2},
                    ],
                },
            },
        ],
    }


def test_compiler_derives_canonical_dijkstra_state_and_events():
    result = compile_algorithm_trace(normalize_dsl(_dijkstra_dsl()))

    report = result["algorithm_trace_compilation"]
    assert report["applied"] is True
    assert report["frames_compiled"] == 3
    assert report["issues"] == []
    final = result["frames"][-1]["state_snapshot"]
    assert final["schema_version"] == "algorithm-trace-v1"
    assert final["algorithm"] == "dijkstra"
    assert final["dist"] == {"s": 0, "a": 3, "b": 1}
    assert final["predecessor"] == {"s": None, "a": "b", "b": "s"}
    assert final["events"]


def test_compiler_does_not_repair_conflicting_semantic_hint():
    dsl = _dijkstra_dsl()
    dsl["frames"][1]["state_snapshot"]["dist"]["a"] = 99
    result = compile_algorithm_trace(normalize_dsl(dsl))

    frame = result["frames"][1]
    assert frame["state_snapshot"]["dist"]["a"] == 99
    assert result["algorithm_trace_compilation"]["issues"]


def test_compiler_reads_legacy_nested_bellman_graph_data():
    graph = {
        "id": "bellman_graph",
        "type": "graph",
        "data": {
            "nodes": ["s", "a", "b"],
            "edges": [
                {"from": "s", "to": "a", "weight": 4},
                {"from": "a", "to": "b", "weight": -2},
            ],
        },
    }
    dsl = {
        "topic": "Bellman-Ford 负权边",
        "frames": [{
            "frame_id": "f_001",
            "title": "初始化",
            "visual_objects": [graph],
            "state_snapshot": {
                "dist": {"s": 0, "a": "∞", "b": "∞"},
                "round": 0,
            },
        }],
    }
    result = compile_algorithm_trace(normalize_dsl(dsl))
    assert result["algorithm_trace_compilation"]["issues"] == []
    assert result["frames"][0]["state_snapshot"]["algorithm"] == "bellman_ford"


def test_compiler_migrates_bfs_and_dfs_traversal_state():
    graph = {
        "id": "primary_graph",
        "type": "graph",
        "nodes": [{"id": "s"}, {"id": "a"}, {"id": "b"}],
        "edges": [
            {"source": "s", "target": "a"},
            {"source": "s", "target": "b"},
        ],
    }
    for topic, algorithm, order, queue in [
        ("BFS 广度优先搜索", "bfs", ["s", "a", "b"], ["a", "b"]),
        ("DFS 深度优先搜索", "dfs", ["s", "a", "b"], ["b", "a"]),
    ]:
        dsl = {
            "topic": topic,
            "frames": [{
                "frame_id": "f_001",
                "title": "访问 s",
                "visual_objects": [graph],
                "state_snapshot": {
                    "visited": ["s"],
                    "queue": queue,
                    "events": [{"operation": "visit", "target": "s"}],
                },
            }],
        }
        result = compile_algorithm_trace(normalize_dsl(dsl))
        assert result["algorithm_trace_compilation"]["issues"] == []
        snapshot = result["frames"][0]["state_snapshot"]
        assert snapshot["algorithm"] == algorithm
        assert snapshot["visited"] == order[:1]
