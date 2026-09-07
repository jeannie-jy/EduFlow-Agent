import pytest

from tools.validate_dsl import check_algorithm_invariants


def _graph_frame(frame_id: str, snapshot: dict) -> dict:
    return {
        "frame_id": frame_id,
        "visual_objects": [
            {
                "id": "graph",
                "type": "graph",
                "nodes": [{"id": "A"}, {"id": "B"}, {"id": "C"}],
                "edges": [
                    {"source": "A", "target": "B", "weight": 1},
                    {"source": "B", "target": "C", "weight": 2},
                ],
            }
        ],
        "state_snapshot": snapshot,
    }


@pytest.mark.asyncio
async def test_dijkstra_tree_edges_must_match_final_distances():
    frames = [
        _graph_frame("f_001", {"dist": {"A": 0, "B": 1, "C": 3}}),
        _graph_frame(
            "f_002",
            {
                "dist": {"A": 0, "B": 1, "C": 3},
                "visited": ["A", "B", "C"],
                "shortest_path_tree": ["A-B", "A-C"],
            },
        ),
    ]

    result = await check_algorithm_invariants(frames, topic="Dijkstra 最短路径")

    assert result["checked"] is True
    assert result["consistent"] is False
    assert any("A->C" in issue["description"] for issue in result["issues"])


@pytest.mark.asyncio
async def test_dijkstra_queue_cannot_disappear_without_dequeue():
    frames = [
        _graph_frame(
            "f_001",
            {"visited": ["A"], "queue": ["F(∞)"]},
        ),
        _graph_frame("f_002", {"visited": ["A"]}),
    ]

    result = await check_algorithm_invariants(frames, topic="演示 Dijkstra 不可达节点")

    assert result["consistent"] is False
    assert any("队列" in issue["description"] for issue in result["issues"])


@pytest.mark.asyncio
async def test_dijkstra_graph_edges_cannot_change_between_frames():
    first = _graph_frame("f_001", {"dist": {"A": 0, "B": 1, "C": 3}})
    second = _graph_frame("f_002", {"dist": {"A": 0, "B": 1, "C": 3}})
    second["visual_objects"][0]["edges"][1]["weight"] = 99

    result = await check_algorithm_invariants(
        [first, second], topic="Dijkstra 最短路径"
    )

    assert result["consistent"] is False
    assert any("图的节点连接或边权" in issue["description"] for issue in result["issues"])


@pytest.mark.asyncio
async def test_secondary_graphs_do_not_reset_primary_trace():
    first = _graph_frame(
        "f_001",
        {"dist": {"A": 0, "B": 1, "C": 3}, "visited": ["A"]},
    )
    secondary = {
        "frame_id": "f_002",
        "visual_objects": [
            {
                "id": "negative_graph",
                "type": "graph",
                "label": "负权边反例",
                "nodes": [{"id": "X"}, {"id": "Y"}],
                "edges": [{"source": "X", "target": "Y", "weight": -1}],
            }
        ],
        "state_snapshot": {"dist": {"X": 0, "Y": -1}, "visited": ["X", "Y"]},
    }
    result = await check_algorithm_invariants(
        [first, secondary], topic="Dijkstra 最短路径"
    )

    assert result["consistent"] is True
    assert result["issues"] == []


@pytest.mark.asyncio
async def test_derived_path_tree_is_checked_against_primary_graph():
    first = _graph_frame(
        "f_001",
        {"dist": {"A": 0, "B": 1, "C": 3}},
    )
    derived = {
        "frame_id": "f_002",
        "visual_objects": [
            {
                "id": "path_tree",
                "type": "graph",
                "graph_role": "derived",
                "nodes": [{"id": "A"}, {"id": "B"}, {"id": "C"}],
                "edges": [
                    {"source": "A", "target": "C", "weight": 9},
                    {"source": "B", "target": "C", "weight": 2},
                ],
            }
        ],
        "state_snapshot": {"dist": {"A": 0, "B": 1, "C": 3}},
    }
    result = await check_algorithm_invariants(
        [first, derived], topic="Dijkstra 最短路径"
    )

    assert result["consistent"] is False
    assert any(issue["frame_id"] == "f_002" for issue in result["issues"])


@pytest.mark.asyncio
async def test_repeated_path_tree_representations_are_not_multiple_predecessors():
    first = _graph_frame(
        "f_001",
        {
            "dist": {"A": 0, "B": 4, "C": 2, "D": 9},
            "shortest_path_tree": {"A": None, "B": "A", "C": "A", "D": "B"},
        },
    )
    first["visual_objects"][0]["nodes"].append({"id": "D"})
    first["visual_objects"][0]["edges"] = [
        {"source": "A", "target": "B", "weight": 4},
        {"source": "A", "target": "C", "weight": 2},
        {"source": "B", "target": "D", "weight": 5},
    ]
    first["visual_objects"].append(
        {
            "id": "path_tree",
            "type": "graph",
            "graph_role": "derived",
            "edges": [
                {"source": "A", "target": "B", "weight": 4},
                {"source": "A", "target": "C", "weight": 2},
                {"source": "B", "target": "D", "weight": 5},
            ],
        }
    )
    second = {
        "frame_id": "f_002",
        "visual_objects": first["visual_objects"],
        "state_snapshot": first["state_snapshot"],
    }

    result = await check_algorithm_invariants(
        [first, second], topic="Dijkstra 最短路径"
    )

    assert result["consistent"] is True
    assert result["issues"] == []


@pytest.mark.asyncio
async def test_non_shortest_path_topic_is_not_overconstrained():
    result = await check_algorithm_invariants(
        [_graph_frame("f_001", {"visited": ["A"]})],
        topic="观察一般图的遍历顺序",
    )

    assert result == {"checked": False, "consistent": True, "issues": []}
