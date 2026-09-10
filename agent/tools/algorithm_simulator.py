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

from schema.algorithm_trace import AlgorithmEvent, AlgorithmState, QueueEntry


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
    queue: list[tuple[str, float] | tuple[str, float, int]],
    predecessor: dict[str, str | None],
    round_index: int | None = None,
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    state = AlgorithmState(
        schema_version="algorithm-trace-v1",
        algorithm=algorithm,
        phase=phase,
        dist={key: _distance_value(value) for key, value in dist.items()},
        visited=list(visited),
        queue=[
            QueueEntry(vertex=item[0], priority=_distance_value(item[1]))
            for item in queue
        ],
        predecessor=deepcopy(predecessor),
        round=round_index,
        events=[AlgorithmEvent.model_validate(event) for event in (events or [])],
    )
    return state.model_dump(mode="json")


def _public_queue(
    queue: list[tuple[str, float, int]],
    dist: dict[str, float],
    visited: list[str],
) -> list[tuple[str, float]]:
    """Expose the logical priority queue, removing stale heap entries.

    The teaching DSL should show one current key per unvisited vertex.  The
    implementation may use lazy deletion internally, but leaking stale
    entries (for example ``A(4)`` after ``A(3)`` was discovered) makes the
    trace appear contradictory and changes tie-breaking between frames.
    """
    output: list[tuple[str, float]] = []
    seen: set[str] = set()
    for vertex, priority, _order in sorted(queue, key=lambda item: (item[1], item[2], item[0])):
        if vertex in visited or vertex in seen:
            continue
        if not math.isclose(priority, dist.get(vertex, math.inf), rel_tol=1e-9, abs_tol=1e-9):
            continue
        seen.add(vertex)
        output.append((vertex, priority))
    return output


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
    insertion_order = 0
    queue: list[tuple[str, float, int]] = [(source, 0.0, insertion_order)]
    snapshots = [_state(
        algorithm="dijkstra", phase="init", dist=dist, visited=visited,
        queue=_public_queue(queue, dist, visited), predecessor=predecessor,
    )]

    while queue:
        queue.sort(key=lambda item: (item[1], item[2], item[0]))
        vertex, priority, _order = queue.pop(0)
        if vertex in visited or priority != dist[vertex]:
            continue
        visited.append(vertex)
        snapshots.append(_state(
            algorithm="dijkstra", phase="select", dist=dist, visited=visited,
            queue=_public_queue(queue, dist, visited), predecessor=predecessor,
            events=[{"operation": "select", "target": vertex}],
        ))
        relax_events: list[dict[str, Any]] = []
        for target, weight in outgoing.get(vertex, []):
            candidate = dist[vertex] + weight
            if candidate < dist[target]:
                dist[target] = candidate
                predecessor[target] = vertex
                insertion_order += 1
                queue.append((target, candidate, insertion_order))
                relax_events.append({
                    "operation": "relax",
                    "source": vertex,
                    "target": target,
                    "weight": int(weight) if weight.is_integer() else weight,
                })
        snapshots.append(_state(
            algorithm="dijkstra", phase="relax", dist=dist, visited=visited,
            queue=_public_queue(queue, dist, visited), predecessor=predecessor,
            events=relax_events,
        ))
    snapshots.append(_state(
        algorithm="dijkstra", phase="summary", dist=dist, visited=visited,
        queue=[], predecessor=predecessor,
        events=[{"operation": "complete"}],
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
        round_events: list[dict[str, Any]] = []
        for edge_source, target, weight in edges:
            if math.isfinite(dist[edge_source]) and dist[edge_source] + weight < dist[target]:
                dist[target] = dist[edge_source] + weight
                predecessor[target] = edge_source
                changed = True
                round_events.append({
                    "operation": "relax",
                    "source": edge_source,
                    "target": target,
                    "weight": int(weight) if weight.is_integer() else weight,
                })
        snapshots.append(_state(
            algorithm="bellman_ford", phase="round", dist=dist, visited=[],
            queue=[], predecessor=predecessor, round_index=round_index,
            events=round_events,
        ))
        if not changed:
            break
    return snapshots


def _traversal_state(
    *,
    algorithm: str,
    phase: str,
    visited: list[str],
    queue: list[str],
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    state = AlgorithmState(
        schema_version="algorithm-trace-v1",
        algorithm=algorithm,
        phase=phase,
        visited=list(visited),
        queue=[QueueEntry(vertex=vertex, priority=None) for vertex in queue],
        events=[AlgorithmEvent.model_validate(event) for event in (events or [])],
    )
    return state.model_dump(mode="json")


def _traversal_graph(graph: dict[str, Any], source: str) -> tuple[list[str], dict[str, list[str]]]:
    edges = _edges(graph)
    vertices = _vertices(graph, edges)
    if source not in vertices:
        raise ValueError(f"source vertex {source!r} is not present in graph")
    outgoing = {vertex: [] for vertex in vertices}
    for edge_source, target, _weight in edges:
        outgoing.setdefault(edge_source, []).append(target)
    return vertices, outgoing


def simulate_bfs(graph: dict[str, Any], source: str) -> list[dict[str, Any]]:
    """Return deterministic FIFO traversal snapshots using graph edge order."""
    _vertices_list, outgoing = _traversal_graph(graph, source)
    visited: list[str] = []
    queue: list[str] = [source]
    discovered = {source}
    snapshots = [_traversal_state(
        algorithm="bfs", phase="init", visited=visited, queue=queue,
    )]
    while queue:
        vertex = queue.pop(0)
        visited.append(vertex)
        events = [{"operation": "dequeue", "target": vertex}, {"operation": "visit", "target": vertex}]
        for target in outgoing.get(vertex, []):
            if target not in discovered:
                discovered.add(target)
                queue.append(target)
                events.append({"operation": "enqueue", "target": target})
        snapshots.append(_traversal_state(
            algorithm="bfs", phase="visit", visited=visited, queue=queue,
            events=events,
        ))
    snapshots.append(_traversal_state(
        algorithm="bfs", phase="summary", visited=visited, queue=[],
        events=[{"operation": "complete"}],
    ))
    return snapshots


def simulate_dfs(graph: dict[str, Any], source: str) -> list[dict[str, Any]]:
    """Return deterministic LIFO traversal snapshots using graph edge order."""
    _vertices_list, outgoing = _traversal_graph(graph, source)
    visited: list[str] = []
    stack: list[str] = [source]
    discovered = {source}
    snapshots = [_traversal_state(
        algorithm="dfs", phase="init", visited=visited, queue=stack,
    )]
    while stack:
        vertex = stack.pop()
        visited.append(vertex)
        events = [{"operation": "dequeue", "target": vertex}, {"operation": "visit", "target": vertex}]
        # Push in reverse edge order so the first declared edge is visited first.
        for target in reversed(outgoing.get(vertex, [])):
            if target not in discovered:
                discovered.add(target)
                stack.append(target)
                events.append({"operation": "enqueue", "target": target})
        snapshots.append(_traversal_state(
            algorithm="dfs", phase="visit", visited=visited, queue=stack,
            events=events,
        ))
    snapshots.append(_traversal_state(
        algorithm="dfs", phase="summary", visited=visited, queue=[],
        events=[{"operation": "complete"}],
    ))
    return snapshots


__all__ = ["simulate_bellman_ford", "simulate_bfs", "simulate_dfs", "simulate_dijkstra"]
