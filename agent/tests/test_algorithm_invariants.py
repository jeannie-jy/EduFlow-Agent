import pytest

from tools.validate_dsl import check_algorithm_invariants, stabilize_algorithm_trace


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
async def test_dijkstra_priority_queue_pair_encoding_uses_vertex_only():
    frames = [
        _graph_frame(
            "f_001",
            {"visited": ["A"], "queue": [["C", 8]]},
        ),
        _graph_frame(
            "f_002",
            {"visited": ["A", "C"], "queue": []},
        ),
    ]

    result = await check_algorithm_invariants(frames, topic="Dijkstra 最短路径")

    assert result["consistent"] is True
    assert result["issues"] == []


@pytest.mark.asyncio
async def test_dijkstra_scalar_empty_queue_sentinel_is_not_a_vertex():
    frames = [
        _graph_frame(
            "f_001",
            {"visited": ["A", "B", "C"], "priority_queue": "empty"},
        ),
        _graph_frame(
            "f_002",
            {"visited": ["A", "B", "C"], "priority_queue": []},
        ),
    ]

    result = await check_algorithm_invariants(frames, topic="Dijkstra 最短路径")

    assert result["consistent"] is True
    assert result["issues"] == []


def _negative_counterexample_frame(
    *, visited: list[str], wrong_dist: dict[str, int]
) -> dict:
    return {
        "frame_id": "f_001",
        "visual_objects": [{
            "id": "negative_graph",
            "type": "graph",
            "graph_role": "secondary",
            "directed": True,
            "nodes": [{"id": "A"}, {"id": "B"}, {"id": "C"}],
            "edges": [
                {"source": "A", "target": "B", "weight": 2},
                {"source": "A", "target": "C", "weight": 1},
                {"source": "C", "target": "B", "weight": -3},
            ],
        }],
        "state_snapshot": {
            "visited_wrong": visited,
            "wrong_dist": wrong_dist,
        },
    }


@pytest.mark.asyncio
async def test_dijkstra_negative_counterexample_rejects_non_minimum_selection():
    frame = _negative_counterexample_frame(
        visited=["A", "B", "C"],
        wrong_dist={"A": 0, "B": 2, "C": 1},
    )

    result = await check_algorithm_invariants([frame], topic="Dijkstra 最短路径")

    assert result["consistent"] is False
    assert any("当前最小距离" in issue["description"] for issue in result["issues"])


@pytest.mark.asyncio
async def test_dijkstra_negative_counterexample_rejects_missing_relaxation():
    frame = _negative_counterexample_frame(
        visited=["A", "C", "B"],
        wrong_dist={"A": 0, "B": 2, "C": 1},
    )

    result = await check_algorithm_invariants([frame], topic="Dijkstra 最短路径")

    assert result["consistent"] is False
    assert any("必要松弛" in issue["description"] for issue in result["issues"])


@pytest.mark.asyncio
async def test_dijkstra_accepts_valid_negative_edge_counterexample_trace():
    frame = _negative_counterexample_frame(
        visited=["A", "B", "C"],
        wrong_dist={"A": 0, "B": 2, "C": 5},
    )
    frame["visual_objects"][0]["edges"][1]["weight"] = 5
    frame["visual_objects"][0]["edges"][2]["weight"] = -10

    result = await check_algorithm_invariants([frame], topic="Dijkstra 最短路径")

    assert result["consistent"] is True
    assert result["issues"] == []


@pytest.mark.asyncio
async def test_dijkstra_may_discard_only_infinite_queue_tail_on_early_stop():
    frames = [
        _graph_frame(
            "f_001",
            {
                "dist": {"A": 0, "B": 1, "C": "∞"},
                "visited": ["A", "B"],
                "queue": ["C(∞)"],
            },
        ),
        _graph_frame(
            "f_002",
            {
                "dist": {"A": 0, "B": 1, "C": "∞"},
                "visited": ["A", "B"],
            },
        ),
    ]

    result = await check_algorithm_invariants(
        frames, topic="演示 Dijkstra 不可达节点"
    )

    assert result["consistent"] is True
    assert result["issues"] == []


@pytest.mark.asyncio
async def test_dijkstra_rejects_infinite_distance_vertex_in_visited():
    frames = [
        _graph_frame(
            "f_001",
            {
                "dist": {"A": 0, "B": 1, "C": "∞"},
                "visited": ["A", "C"],
            },
        )
    ]

    result = await check_algorithm_invariants(
        frames, topic="演示 Dijkstra 不可达节点"
    )

    assert result["consistent"] is False
    assert any("不可达顶点" in issue["description"] for issue in result["issues"])


def test_dijkstra_guardrail_filters_unreachable_and_prevents_visited_regression():
    dsl = {
        "topic": "Dijkstra 不可达节点",
        "frames": [
            _graph_frame(
                "f_001",
                {
                    "dist": {"A": 0, "B": 1, "C": "∞"},
                    "visited": ["A", "B"],
                },
            ),
            _graph_frame(
                "f_002",
                {
                    "dist": {"A": 0, "B": 1, "C": "∞"},
                    "visited": ["A", "B", "C"],
                },
            ),
            _graph_frame(
                "f_003",
                {
                    "dist": {"A": 0, "B": 1, "C": "∞"},
                    "visited": ["A"],
                },
            ),
        ],
    }

    stabilized = stabilize_algorithm_trace(dsl)

    assert dsl["frames"][1]["state_snapshot"]["visited"] == ["A", "B", "C"]
    assert [
        frame["state_snapshot"]["visited"] for frame in stabilized["frames"]
    ] == [["A", "B"], ["A", "B"], ["A", "B"]]


def test_secondary_trace_cannot_reset_primary_guardrail_baseline():
    first = _graph_frame(
        "f_001",
        {"dist": {"A": 0, "B": 1, "C": 3}, "visited": ["A", "B"]},
    )
    secondary = {
        "frame_id": "f_002",
        "visual_objects": [
            {
                "id": "practice_graph",
                "type": "graph",
                "graph_role": "secondary",
                "nodes": [{"id": "X"}, {"id": "Y"}],
                "edges": [{"source": "X", "target": "Y", "weight": 2}],
            }
        ],
        "state_snapshot": {"dist": {"X": 0, "Y": 2}, "visited": ["X", "Y"]},
    }
    resumed = _graph_frame(
        "f_003",
        {"dist": {"A": 0, "B": 1, "C": 3}, "visited": ["A"]},
    )

    stabilized = stabilize_algorithm_trace({
        "topic": "Dijkstra 最短路径",
        "frames": [first, secondary, resumed],
    })

    assert stabilized["frames"][1]["state_snapshot"]["visited"] == ["X", "Y"]
    assert stabilized["frames"][2]["state_snapshot"]["visited"] == ["A", "B"]


def test_bellman_ford_guardrail_repairs_in_place_round_values_and_table():
    graph = {
        "id": "primary_graph",
        "type": "graph",
        "graph_role": "primary",
        "nodes": [{"id": "s"}, {"id": "a"}, {"id": "b"}, {"id": "c"}],
        "edges": [
            {"source": "s", "target": "a", "weight": 6},
            {"source": "s", "target": "b", "weight": 7},
            {"source": "a", "target": "c", "weight": 5},
            {"source": "b", "target": "c", "weight": -3},
            {"source": "c", "target": "a", "weight": 1},
        ],
    }
    dsl = {
        "topic": "讲解 Bellman-Ford 迭代松弛",
        "frames": [{
            "frame_id": "f_001",
            "visual_objects": [graph, {
                "id": "dist_table",
                "type": "table",
                "headers": ["轮次", "s", "a", "b", "c"],
                "rows": [["第1轮", 0, 6, 7, 16]],
            }],
            "state_snapshot": {
                "round": 1,
                "dist": {"s": 0, "a": 6, "b": 7, "c": 16},
            },
            "narration": "第 1 轮后 dist[a]=6, dist[b]=7, dist[c]=16。",
        }],
    }

    stabilized = stabilize_algorithm_trace(dsl)
    frame = stabilized["frames"][0]

    assert frame["state_snapshot"]["dist"]["c"] == 4
    assert frame["visual_objects"][1]["rows"][0][-1] == 4
    assert "dist[c]=4" in frame["narration"]


@pytest.mark.asyncio
async def test_bellman_ford_legacy_graph_aliases_ignore_comparison_and_summary_frames():
    """Legacy vertices/from/to output must not trigger Dijkstra reset errors."""
    frames = [
        {
            "frame_id": "f_001",
            "visual_objects": [{
                "id": "vo_g1",
                "type": "graph",
                "vertices": ["s", "a", "b"],
                "edges": [{"from": "s", "to": "a", "weight": 2}],
            }],
            "state_snapshot": {
                "phase": "dijkstra_failure_demo",
                "dist": {"s": 0, "a": 2, "b": 5},
            },
        },
        {
            "frame_id": "f_003",
            "state_snapshot": {"phase": "init", "dist": {"s": 0, "a": "∞", "b": "∞"}},
        },
        {
            "frame_id": "f_005",
            "visual_objects": [{
                "id": "bellman_graph",
                "type": "graph",
                "vertices": ["s", "a", "b"],
                "edges": [
                    {"from": "s", "to": "a", "weight": 2},
                    {"from": "a", "to": "b", "weight": -1},
                ],
            }],
            "state_snapshot": {"dist": {"s": 0, "a": 2, "b": 1}},
        },
    ]

    result = await check_algorithm_invariants(
        frames, topic="讲解 Bellman-Ford 如何处理负权边并检测负环"
    )

    assert result["checked"] is True
    assert result["consistent"] is True
    assert result["issues"] == []


def test_dijkstra_guardrail_rebuilds_tree_from_consistent_predecessors():
    dsl = {
        "topic": "用逐帧方式讲解 Dijkstra 最短路径算法",
        "frames": [{
            "frame_id": "f_001",
            "visual_objects": [{
                "id": "primary_graph",
                "type": "graph",
                "nodes": [{"id": "A"}, {"id": "B"}, {"id": "C"}],
                "edges": [
                    {"source": "A", "target": "C", "weight": 2},
                    {"source": "B", "target": "C", "weight": 1},
                ],
            }, {
                "id": "shortest_path_tree",
                "type": "graph",
                "nodes": [{"id": "A"}, {"id": "B"}, {"id": "C"}],
                "edges": [
                    {"source": "A", "target": "C", "weight": 2},
                    {"source": "B", "target": "C", "weight": 1},
                ],
            }],
            "state_snapshot": {
                "dist": {"A": 0, "B": 3, "C": 2},
                "prev": {"C": "A"},
                "shortest_path_tree": [
                    {"source": "A", "target": "C", "weight": 2},
                    {"source": "B", "target": "C", "weight": 1},
                ],
            },
        }],
    }

    stabilized = stabilize_algorithm_trace(dsl)
    frame = stabilized["frames"][0]

    assert frame["state_snapshot"]["shortest_path_tree"] == [
        {"source": "A", "target": "C", "weight": 2}
    ]
    derived = frame["visual_objects"][1]
    assert derived["edges"] == frame["state_snapshot"]["shortest_path_tree"]


def test_mixed_primary_secondary_frame_still_stabilizes_primary_snapshot():
    first = _graph_frame(
        "f_001",
        {"dist": {"A": 0, "B": 1, "C": "∞"}, "visited": ["A", "B"]},
    )
    mixed = _graph_frame(
        "f_002",
        {
            "dist": {"A": 0, "B": 1, "C": "∞"},
            "visited": ["A", "B", "C"],
        },
    )
    mixed["visual_objects"].append({
        "id": "practice_graph",
        "type": "graph",
        "graph_role": "secondary",
        "nodes": [{"id": "X"}, {"id": "Y"}],
        "edges": [{"source": "X", "target": "Y", "weight": 2}],
    })

    stabilized = stabilize_algorithm_trace({
        "topic": "Dijkstra 最短路径",
        "frames": [first, mixed],
    })

    assert stabilized["frames"][1]["state_snapshot"]["visited"] == ["A", "B"]


def test_guardrail_clamps_primary_distance_regression():
    first = _graph_frame(
        "f_001",
        {"dist": {"A": 0, "B": 1, "C": 3}, "visited": ["A", "B"]},
    )
    second = _graph_frame(
        "f_002",
        {"dist": {"A": 0, "B": 2, "C": 5}, "visited": ["A", "B", "C"]},
    )

    stabilized = stabilize_algorithm_trace({
        "topic": "Dijkstra 最短路径",
        "frames": [first, second],
    })

    assert stabilized["frames"][1]["state_snapshot"]["dist"] == {
        "A": 0,
        "B": 1,
        "C": 3,
    }


def test_unrequested_negative_counterexample_is_removed_from_primary_trace():
    primary = _graph_frame(
        "f_001",
        {"dist": {"A": 0, "B": 1, "C": 3}, "visited": ["A", "B"]},
    )
    mixed = {
        "frame_id": "f_002",
        "visual_objects": [
            primary["visual_objects"][0],
            {
                "id": "negative_graph",
                "type": "graph",
                "graph_role": "secondary",
                "nodes": [{"id": "A"}, {"id": "B"}, {"id": "C"}],
                "edges": [
                    {"source": "A", "target": "B", "weight": 2},
                    {"source": "A", "target": "C", "weight": 5},
                    {"source": "C", "target": "B", "weight": -4},
                ],
            },
        ],
        "state_snapshot": {
            "dist": {"A": 0, "B": 2, "C": 5},
            "visited": ["A", "B", "C"],
        },
    }

    stabilized = stabilize_algorithm_trace({
        "topic": "Dijkstra 为什么要求非负边权",
        "frames": [primary, mixed],
    })

    assert len(stabilized["frames"]) == 1
    assert all(
        not (
            visual.get("type") == "graph"
            and any(float(edge.get("weight", 0)) < 0 for edge in visual.get("edges", []))
        )
        for frame in stabilized["frames"]
        for visual in frame.get("visual_objects", [])
        if isinstance(visual, dict)
    )


def test_unrequested_negative_primary_frames_are_dropped():
    positive = _graph_frame(
        "f_001",
        {"dist": {"A": 0, "B": 1, "C": 3}, "visited": ["A"]},
    )
    negative = _graph_frame(
        "f_002",
        {"dist": {"A": 0, "B": -9, "C": 1}, "visited": ["A", "C", "B"]},
    )
    negative["visual_objects"][0]["edges"] = [
        {"source": "A", "target": "B", "weight": 5},
        {"source": "A", "target": "C", "weight": 1},
        {"source": "C", "target": "B", "weight": -10},
    ]

    stabilized = stabilize_algorithm_trace({
        "topic": "Dijkstra 为什么要求非负边权",
        "frames": [positive, negative],
    })

    assert [frame["frame_id"] for frame in stabilized["frames"]] == ["f_001"]


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
