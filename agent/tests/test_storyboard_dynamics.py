from tools.validate_dsl import check_storyboard_dynamics


def _frame(frame_id: str, algorithm: str, visited: list[str], *, graph: bool = True):
    visuals = []
    if graph:
        visuals.append({
            "id": "primary_graph",
            "type": "graph",
            "graph_role": "primary",
            "nodes": [{"id": "A"}, {"id": "B"}, {"id": "C"}],
            "edges": [],
        })
    return {
        "frame_id": frame_id,
        "title": f"{algorithm.upper()} 演示",
        "visual_objects": visuals,
        "state_snapshot": {
            "algorithm": algorithm,
            "visited": visited,
            "queue": [],
        },
    }


def test_bfs_and_dfs_storyboard_requires_progress_for_both_algorithms():
    frames = [
        _frame("f_001", "bfs", ["A", "B", "C"]),
        _frame("f_002", "dfs", ["A", "B", "C"]),
    ]

    result = check_storyboard_dynamics(frames, topic="BFS与DFS")

    assert result["checked"] is True
    assert result["dynamic"] is False
    assert {issue["algorithm"] for issue in result["issues"]} == {"bfs", "dfs"}


def test_bfs_and_dfs_storyboard_accepts_three_visible_states_each():
    frames = [
        _frame("f_001", "bfs", ["A"]),
        _frame("f_002", "bfs", ["A", "B"]),
        _frame("f_003", "bfs", ["A", "B", "C"]),
        _frame("f_004", "dfs", ["A"]),
        _frame("f_005", "dfs", ["A", "C"]),
        _frame("f_006", "dfs", ["A", "C", "B"]),
    ]

    result = check_storyboard_dynamics(frames, topic="BFS与DFS")

    assert result["dynamic"] is True
    assert result["issues"] == []


def test_execution_states_without_primary_graph_are_rejected():
    frames = [
        _frame("f_001", "bfs", ["A"], graph=False),
        _frame("f_002", "bfs", ["A", "B"], graph=False),
        _frame("f_003", "bfs", ["A", "B", "C"], graph=False),
    ]

    result = check_storyboard_dynamics(frames, topic="BFS")

    assert result["dynamic"] is False
    assert any("primary_graph" in issue["description"] for issue in result["issues"])


def test_non_traversal_topic_is_not_subject_to_motion_gate():
    result = check_storyboard_dynamics([], topic="哈希表概览")

    assert result == {"checked": False, "dynamic": True, "issues": []}


def test_sorting_storyboard_requires_multiple_array_states():
    frames = [
        {
            "frame_id": "f_001",
            "visual_objects": [{"id": "arr", "type": "array", "cells": [{"value": 3}, {"value": 1}]}],
            "state_snapshot": {"array": [3, 1]},
        },
        {
            "frame_id": "f_002",
            "visual_objects": [{"id": "arr", "type": "array", "cells": [{"value": 1}, {"value": 3}]}],
            "state_snapshot": {"array": [1, 3]},
        },
    ]

    result = check_storyboard_dynamics(frames, topic="冒泡排序")

    assert result["checked"] is True
    assert result["dynamic"] is False
    assert any("3 个" in issue["description"] for issue in result["issues"])


def test_non_code_algorithm_rejects_code_on_every_scene():
    frames = [
        {
            "frame_id": f"f_{index:03d}",
            "title": "Dijkstra 演示",
            "visual_objects": [
                {"id": "primary_graph", "type": "graph", "graph_role": "primary"},
                {"id": "code", "type": "code_block", "code": "relax()"},
            ],
            "state_snapshot": {
                "algorithm": "dijkstra",
                "dist": {"A": 0, "B": 4 - index},
                "visited": ["A"] if index == 1 else ["A", "B"],
            },
        }
        for index in range(1, 4)
    ]

    result = check_storyboard_dynamics(frames, topic="Dijkstra 最短路径")

    assert result["dynamic"] is False
    assert any("代码镜头" in issue["description"] for issue in result["issues"])
    assert result["metrics"]["code_scene_count"] == 3
