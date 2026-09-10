"""Deterministic state derivation for algorithm teaching traces.

The LLM may select which operation to explain, but these simulators derive
distances, queues, visited sets and predecessors from the graph.  They are
deliberately side-effect free so they can be used by offline replay before
being connected to the production Coder.
"""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

from schema.algorithm_trace import AlgorithmState, QueueEntry


def _edges(graph: dict[str, Any]) -> list[tuple[str, str, float]]:
    raw_edges = graph.get("edges", graph.get("graph_edges", []))
    result: list[tuple[str, str, float]] = []
    for edge in raw_edges if isinstance(raw_edges, list) else []:
        if not isinstance(edge, dict):
            continue
        source = edge.get("source", edge.get("from"))
        target = edge.get("target", edge.get("to"))
        weight = edge.get("weight")
        if source is None or target is None:
            continue
        try:
            numeric_weight = float(weight)
        except (TypeError, ValueError):
            continue
        if math.isfinite(numeric_weight):
            result.append((str(source), str(target), numeric_weight))
    return result


def _vertices(graph: dict[str, Any], edges: list[tuple[str, str, float]]) -> list[str]:
    raw_nodes = graph.get("nodes") or graph.get("vertices", [])
    values: list[str] = []
    for node in raw_nodes if isinstance(raw_nodes, list) else []:
        if isinstance(node, dict):
            node = node.get("id", node.get("label"))
        if node is not None and str(node) not in values:
            values.append(str(node))
    for source, target, _ in edges:
        if source not in values:
            values.append(source)
        if target not in values:
            values.append(target)
    return values


def _distance_value(value: float) -> float | str:
    return "∞" if math.isinf(value) else int(value) if value.is_integer() else value


def _state(
    *,
    algorithm: str,
    phase: str,
    dist: dict[str, float],
    visited: list[str],
    queue: list[tuple[str, float]],
    predecessor: dict[str, str | None],
    round_index: int | None = None,
) -> dict[str, Any]:
    state = AlgorithmState(
        schema_version="algorithm-trace-v1",
        algorithm=algorithm,
        phase=phase,
        dist={key: _distance_value(value) for key, value in dist.items()},
        visited=list(visited),
        queue=[QueueEntry(vertex=vertex, priority=_distance_value(priority)) for vertex, priority in queue],
        predecessor=deepcopy(predecessor),
        round=round_index,
    )
    return state.model_dump(mode="json")


def simulate_dijkstra(graph: dict[str, Any], source: str) -> list[dict[str, Any]]:
    """Return deterministic Dijkstra snapshots using lexical tie-breaking."""
    edges = _edges(graph)
    vertices = _vertices(graph, edges)
    if source not in vertices:
        raise ValueError(f"source vertex {source!r} is not present in graph")
    outgoing: dict[str, list[tuple[str, float]]] = {vertex: [] for vertex in vertices}
    for edge_source, target, weight in edges:
        if weight < 0:
            raise ValueError("Dijkstra requires non-negative edge weights")
        outgoing.setdefault(edge_source, []).append((target, weight))

    dist = {vertex: math.inf for vertex in vertices}
    dist[source] = 0.0
    predecessor: dict[str, str | None] = {vertex: None for vertex in vertices}
    visited: list[str] = []
    queue: list[tuple[str, float]] = [(source, 0.0)]
    snapshots = [_state(
        algorithm="dijkstra", phase="init", dist=dist, visited=visited,
        queue=queue, predecessor=predecessor,
    )]

    while queue:
        queue.sort(key=lambda item: (item[1], item[0]))
        vertex, priority = queue.pop(0)
        if vertex in visited or priority != dist[vertex]:
            continue
        visited.append(vertex)
        snapshots.append(_state(
            algorithm="dijkstra", phase="select", dist=dist, visited=visited,
            queue=queue, predecessor=predecessor,
        ))
        for target, weight in outgoing.get(vertex, []):
            candidate = dist[vertex] + weight
            if candidate < dist[target]:
                dist[target] = candidate
                predecessor[target] = vertex
                queue.append((target, candidate))
        snapshots.append(_state(
            algorithm="dijkstra", phase="relax", dist=dist, visited=visited,
            queue=queue, predecessor=predecessor,
        ))
    snapshots.append(_state(
        algorithm="dijkstra", phase="summary", dist=dist, visited=visited,
        queue=[], predecessor=predecessor,
    ))
    return snapshots


def simulate_bellman_ford(graph: dict[str, Any], source: str) -> list[dict[str, Any]]:
    """Return one deterministic snapshot per Bellman-Ford relaxation round."""
    edges = _edges(graph)
    vertices = _vertices(graph, edges)
    if source not in vertices:
        raise ValueError(f"source vertex {source!r} is not present in graph")
    dist = {vertex: math.inf for vertex in vertices}
    dist[source] = 0.0
    predecessor: dict[str, str | None] = {vertex: None for vertex in vertices}
    snapshots = [_state(
        algorithm="bellman_ford", phase="init", dist=dist, visited=[],
        queue=[], predecessor=predecessor, round_index=0,
    )]
    for round_index in range(1, max(1, len(vertices))):
        changed = False
        for edge_source, target, weight in edges:
            if math.isfinite(dist[edge_source]) and dist[edge_source] + weight < dist[target]:
                dist[target] = dist[edge_source] + weight
                predecessor[target] = edge_source
                changed = True
        snapshots.append(_state(
            algorithm="bellman_ford", phase="round", dist=dist, visited=[],
            queue=[], predecessor=predecessor, round_index=round_index,
        ))
        if not changed:
            break
    return snapshots


__all__ = ["simulate_bellman_ford", "simulate_dijkstra"]
