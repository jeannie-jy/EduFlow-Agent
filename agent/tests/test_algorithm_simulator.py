from __future__ import annotations

import pytest

from tools.algorithm_simulator import simulate_bellman_ford, simulate_dijkstra


GRAPH = {
    "vertices": ["s", "a", "b", "c"],
    "edges": [
        {"from": "s", "to": "a", "weight": 4},
        {"from": "s", "to": "b", "weight": 1},
        {"from": "b", "to": "a", "weight": 2},
        {"from": "a", "to": "c", "weight": 1},
        {"from": "b", "to": "c", "weight": 5},
    ],
}


def test_dijkstra_derives_state_from_graph_and_uses_stable_queue_objects():
    states = simulate_dijkstra(GRAPH, "s")
    final = states[-1]

    assert final["schema_version"] == "algorithm-trace-v1"
    assert final["algorithm"] == "dijkstra"
    assert final["dist"] == {"s": 0, "a": 3, "b": 1, "c": 4}
    assert final["predecessor"] == {"s": None, "a": "b", "b": "s", "c": "a"}
    assert final["queue"] == []
    assert all(isinstance(entry, dict) for state in states for entry in state["queue"])


def test_dijkstra_rejects_negative_edges_before_generating_invalid_states():
    graph = {"vertices": ["s", "a"], "edges": [{"source": "s", "target": "a", "weight": -1}]}

    with pytest.raises(ValueError, match="non-negative"):
        simulate_dijkstra(graph, "s")


def test_bellman_ford_derives_round_states_and_supports_negative_edges():
    graph = {
        "vertices": ["s", "a", "b"],
        "edges": [
            {"source": "s", "target": "a", "weight": 4},
            {"source": "s", "target": "b", "weight": 5},
            {"source": "a", "target": "b", "weight": -2},
        ],
    }

    states = simulate_bellman_ford(graph, "s")

    assert states[-1]["algorithm"] == "bellman_ford"
    assert states[-1]["dist"] == {"s": 0, "a": 4, "b": 2}
    assert [state["round"] for state in states] == [0, 1, 2]
