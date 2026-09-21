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
    result = check_storyboard_dynamics([], topic="冒泡排序")

    assert result == {"checked": False, "dynamic": True, "issues": []}
