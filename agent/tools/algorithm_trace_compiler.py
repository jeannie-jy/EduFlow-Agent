"""Compile model-authored algorithm hints into deterministic trace state.

The Coder is still responsible for the lesson structure, narration and
visual emphasis.  It must not be the source of truth for executable graph
state.  This module is the boundary between those concerns:

* an ``events`` list is treated as an operation proposal and checked against
  the deterministic simulator;
* legacy artifacts without events are aligned to the simulator only when all
  supplied semantic hints agree with the derived state;
* a conflicting hint is never silently repaired.  The original snapshot is
  retained and a hard diagnostic is emitted in the compilation report.

The compiler migrates the graph algorithms with deterministic simulators
(Dijkstra, Bellman-Ford, BFS and DFS). Other topics continue through the
generic DSL path until their state machines are added.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from copy import deepcopy
from typing import Any

from tools.algorithm_simulator import (
    simulate_bellman_ford,
    simulate_bfs,
    simulate_dfs,
    simulate_dijkstra,
)


_ALGORITHM_MARKERS = {
    "dijkstra": ("dijkstra",),
    "bellman_ford": ("bellman-ford", "bellman ford", "bellmanford"),
    "bfs": ("bfs", "广度优先"),
    "dfs": ("dfs", "深度优先"),
}
_SECONDARY_MARKERS = (
    "negative",
    "counterexample",
    "practice",
    "exercise",
    "反例",
    "练习",
    "负环",
)
_GRAPH_DERIVED_MARKERS = ("path_tree", "path-tree", "shortest_path_tree", "路径树")


def _text(value: Any) -> str:
    return str(value or "")


def _algorithm(topic: Any, frames: list[dict[str, Any]]) -> str | None:
    text = _text(topic).casefold()
    for name, markers in _ALGORITHM_MARKERS.items():
        if any(marker in text for marker in markers):
            return name
    for frame in frames:
        snapshot = frame.get("state_snapshot") if isinstance(frame, dict) else None
        if isinstance(snapshot, dict) and snapshot.get("algorithm") in _ALGORITHM_MARKERS:
            return str(snapshot["algorithm"])
    return None


def _graph_role(graph: dict[str, Any]) -> str:
    declared = graph.get("graph_role", graph.get("role"))
    if isinstance(declared, str):
        normalized = declared.strip().casefold().replace("-", "_")
        if normalized in {"secondary", "counterexample", "practice", "exercise", "example"}:
            return "secondary"
        if normalized in {"derived", "path_tree", "view"}:
            return "derived"
        if normalized in {"primary", "state", "main"}:
            return "primary"
    identity = " ".join(_text(graph.get(key)) for key in ("id", "label", "title")).casefold()
    if any(marker in identity for marker in _GRAPH_DERIVED_MARKERS):
        return "derived"
    if any(marker in identity for marker in _SECONDARY_MARKERS):
        return "secondary"
    return "primary"


def _graph_data(graph: dict[str, Any]) -> dict[str, Any]:
    data = graph.get("data")
    return data if isinstance(data, dict) else {}


def _graph_nodes(graph: dict[str, Any]) -> list[Any]:
    data = _graph_data(graph)
    values = graph.get("nodes") or graph.get("vertices") or data.get("nodes") or data.get("vertices")
    return values if isinstance(values, list) else []


def _graph_edges(graph: dict[str, Any]) -> list[dict[str, Any]]:
    data = _graph_data(graph)
    values = graph.get("edges") or graph.get("graph_edges") or data.get("edges") or data.get("graph_edges")
    return [value for value in values if isinstance(value, dict)] if isinstance(values, list) else []


def _canonical_graph(graph: dict[str, Any]) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    for node in _graph_nodes(graph):
        if isinstance(node, dict):
            vertex = node.get("id", node.get("label"))
        else:
            vertex = node
        if vertex is not None and str(vertex) not in {item["id"] for item in nodes}:
            nodes.append({"id": str(vertex)})
    edges: list[dict[str, Any]] = []
    for edge in _graph_edges(graph):
        source = edge.get("source", edge.get("from"))
        target = edge.get("target", edge.get("to"))
        if source is None or target is None:
            continue
        weight = edge.get("weight", 1)
        try:
            numeric = float(weight)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(numeric):
            continue
        edges.append({
            "source": str(source),
            "target": str(target),
            "weight": int(numeric) if numeric.is_integer() else numeric,
        })
        for vertex in (str(source), str(target)):
            if vertex not in {item["id"] for item in nodes}:
                nodes.append({"id": vertex})
        if graph.get("directed") is False:
            edges.append({
                "source": str(target),
                "target": str(source),
                "weight": int(numeric) if numeric.is_integer() else numeric,
            })
    return {"nodes": nodes, "edges": edges}


def _primary_graph(frames: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates: list[tuple[int, int, dict[str, Any]]] = []
    for frame_index, frame in enumerate(frames):
        if not isinstance(frame, dict):
            continue
        for visual in frame.get("visual_objects", []):
            if not isinstance(visual, dict) or visual.get("type") != "graph":
                continue
            if _graph_role(visual) != "primary":
                continue
            graph = _canonical_graph(visual)
            if graph["edges"]:
                candidates.append((len(graph["edges"]), -frame_index, graph))
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item[0], item[1]))[2]


def _distance(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(float(value)) else math.inf
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"∞", "inf", "+inf", "infinity", "无穷", "无穷大"}:
            return math.inf
        try:
            number = float(normalized)
        except ValueError:
            return None
        return number if math.isfinite(number) else math.inf
    return None


def _same_distance(left: Any, right: Any) -> bool:
    left_value, right_value = _distance(left), _distance(right)
    if left_value is None or right_value is None:
        return False
    if math.isinf(left_value) or math.isinf(right_value):
        return math.isinf(left_value) and math.isinf(right_value)
    return math.isclose(left_value, right_value, rel_tol=1e-9, abs_tol=1e-9)


def _source(frames: list[dict[str, Any]], graph: dict[str, Any]) -> str | None:
    for frame in frames:
        snapshot = frame.get("state_snapshot") if isinstance(frame, dict) else None
        if not isinstance(snapshot, dict):
            continue
        if snapshot.get("source") is not None:
            return str(snapshot["source"])
        dist = snapshot.get("dist", snapshot.get("distances", snapshot.get("distance")))
        if isinstance(dist, dict):
            for vertex, value in dist.items():
                if _distance(value) == 0:
                    return str(vertex)
    nodes = graph.get("nodes", [])
    return str(nodes[0]["id"]) if nodes else None


def _state_dist(state: dict[str, Any]) -> dict[str, Any]:
    value = state.get("dist", {})
    return value if isinstance(value, dict) else {}


def _queue_signature(value: Any) -> Counter[tuple[str, str]]:
    entries: list[Any] = value if isinstance(value, list) else []
    output: Counter[tuple[str, str]] = Counter()
    for entry in entries:
        if isinstance(entry, dict):
            vertex = entry.get("vertex", entry.get("node", entry.get("id")))
            priority = entry.get("priority", entry.get("distance", entry.get("key")))
        elif isinstance(entry, (list, tuple)):
            vertex = entry[0] if entry else None
            priority = entry[1] if len(entry) > 1 else None
        elif isinstance(entry, str):
            match = re.fullmatch(r"(.+?)\s*\(([^()]*)\)", entry.strip())
            vertex, priority = (match.group(1), match.group(2)) if match else (entry, None)
        else:
            vertex, priority = entry, None
        if vertex is None:
            continue
        output[(str(vertex), str(priority))] += 1
    return output


def _compatible_hint(
    snapshot: dict[str, Any],
    expected: dict[str, Any],
    *,
    algorithm: str | None = None,
) -> list[str]:
    """Check supplied executable values without requiring optional fields."""
    issues: list[str] = []
    raw_dist = snapshot.get("dist", snapshot.get("distances", snapshot.get("distance")))
    expected_dist = _state_dist(expected)
    raw_queue = snapshot.get("queue", snapshot.get("priority_queue", snapshot.get("heap")))
    queue_signature = _queue_signature(raw_queue)
    expected_queue_signature = _queue_signature(expected.get("queue", []))
    if isinstance(raw_dist, dict):
        for vertex, value in raw_dist.items():
            if vertex not in expected_dist:
                issues.append(f"dist contains unknown vertex {vertex}")
            elif not _same_distance(value, expected_dist[vertex]):
                # A common teaching frame combines "select" and the
                # following relaxations: dist is still shown as ∞ while the
                # queue already contains the newly discovered key.  This is
                # incomplete presentation data, not a contradictory fact;
                # the compiler fills it from the deterministic state.
                expected_value = _distance(expected_dist[vertex])
                raw_value = _distance(value)
                has_queued_value = any(
                    queued_vertex == str(vertex)
                    and _same_distance(priority, expected_value)
                    for queued_vertex, priority_text in queue_signature
                    for priority in (priority_text,)
                )
                if not (
                    raw_value is not None
                    and math.isinf(raw_value)
                    and expected_value is not None
                    and not math.isinf(expected_value)
                    and has_queued_value
                ):
                    issues.append(f"dist[{vertex}] conflicts with deterministic state")
    for key in ("visited", "processed"):
        if isinstance(snapshot.get(key), list) and snapshot[key] != expected.get("visited", []):
            issues.append(f"{key} conflicts with deterministic visited order")
            break
    if isinstance(raw_queue, list) and algorithm == "bellman_ford":
        # Bellman-Ford's edge_scan is presentation metadata.  Its executable
        # state is derived from the deterministic relaxation simulator.
        raw_queue = []
        queue_signature = Counter()
        expected_queue_signature = Counter()
    if isinstance(raw_queue, list):
        if algorithm in {"bfs", "dfs"}:
            raw_vertices = [entry[0] for entry in queue_signature.elements()]
            expected_vertices = [entry[0] for entry in expected_queue_signature.elements()]
            if raw_vertices != expected_vertices:
                issues.append("queue order conflicts with deterministic state")
        elif queue_signature != expected_queue_signature:
            issues.append("queue entries conflict with deterministic state")
    raw_prev = snapshot.get("predecessor", snapshot.get("prev", snapshot.get("predecessors", snapshot.get("parents"))))
    expected_prev = expected.get("predecessor", {})
    if isinstance(raw_prev, dict):
        for vertex, value in raw_prev.items():
            if str(vertex) not in expected_prev or expected_prev[str(vertex)] != value:
                issues.append(f"predecessor[{vertex}] conflicts with deterministic state")
    return issues


def _phase_hint(frame: dict[str, Any], snapshot: dict[str, Any]) -> str:
    phase = _text(snapshot.get("phase")).casefold()
    title = _text(frame.get("title")).casefold()
    narration = _text(frame.get("narration")).casefold()
    if phase in {"summary", "complete", "done"} or any(token in title for token in ("总结", "终止", "路径还原", "summary", "complete")):
        return "summary"
    if phase in {"init", "initial", "initialization"} or any(token in title for token in ("初始化", "initial")):
        return "init"
    if any(token in title for token in ("松弛", "relax")):
        return "relax"
    if any(token in title for token in ("取出", "选择", "select", "dequeue")):
        return "relax"
    if any(token in narration for token in ("summary", "总结")):
        return "summary"
    return phase


def _state_for_frame(
    frame: dict[str, Any],
    snapshot: dict[str, Any],
    states: list[dict[str, Any]],
    *,
    algorithm: str,
) -> dict[str, Any] | None:
    events = snapshot.get("events")
    if algorithm == "bellman_ford" and snapshot.get("round") is not None:
        try:
            round_value = int(snapshot["round"])
        except (TypeError, ValueError):
            round_value = None
        if round_value is not None and states:
            # The simulator exposes initial + V-1 relaxation states; a
            # V-th negative-cycle check is represented by the final stable
            # state rather than by inventing another distance snapshot.
            target_round = max(0, min(round_value, len(states) - 1))
            return states[target_round]
    if isinstance(events, list) and events:
        if any(isinstance(event, dict) and event.get("operation") == "complete" for event in events):
            return states[-1]
        selected_targets = [
            str(event.get("target", event.get("source")))
            for event in events
            if isinstance(event, dict)
            and event.get("operation") in {"select", "dequeue", "visit"}
            and (event.get("target") is not None or event.get("source") is not None)
        ]
        if selected_targets:
            for state in reversed(states):
                if state.get("phase") in {"relax", "visit", "select"} and state.get("visited", [])[-1:] == [selected_targets[-1]]:
                    return state
        relax_sources = [
            str(event.get("source"))
            for event in events
            if isinstance(event, dict) and event.get("operation") == "relax" and event.get("source") is not None
        ]
        if relax_sources:
            for state in reversed(states):
                if state.get("phase") in {"relax", "visit", "select"} and state.get("visited", [])[-1:] == [relax_sources[0]]:
                    return state
        phase = _phase_hint(frame, snapshot)
        matching = [state for state in states if state.get("phase") == phase]
        if matching:
            return matching[-1]

    phase = _phase_hint(frame, snapshot)
    if phase == "init":
        return states[0]
    if phase == "summary":
        return states[-1]

    current = snapshot.get("current")
    if current is not None:
        vertex = str(current)
        for state in reversed(states):
            if state.get("phase") in {"relax", "visit", "select"} and state.get("visited", []) and state["visited"][-1] == vertex:
                return state

    visited = snapshot.get("visited", snapshot.get("processed"))
    if isinstance(visited, list):
        for state in reversed(states):
            if state.get("visited", []) == [str(item) for item in visited]:
                return state

    raw_dist = snapshot.get("dist", snapshot.get("distances", snapshot.get("distance")))
    if isinstance(raw_dist, dict):
        candidates = []
        for state in states:
            matches = sum(
                1 for vertex, value in raw_dist.items()
                if vertex in _state_dist(state) and _same_distance(value, _state_dist(state)[vertex])
            )
            if matches:
                candidates.append((matches, state))
        if candidates:
            return max(candidates, key=lambda item: item[0])[1]
    return states[-1] if algorithm == "bellman_ford" and phase == "summary" else None


def _merge_expected(snapshot: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    preserved = {
        key: deepcopy(value)
        for key, value in snapshot.items()
        if key not in {
            "schema_version", "algorithm", "phase", "dist", "distances", "distance",
            "visited", "processed", "queue", "priority_queue", "heap", "unvisited",
            "predecessor", "prev", "predecessors", "parents", "parent", "round", "events",
        }
    }
    result = dict(preserved)
    result.update(deepcopy(expected))
    return result


def _event_issues(snapshot: dict[str, Any], graph: dict[str, Any], *, algorithm: str) -> list[str]:
    events = snapshot.get("events")
    if not isinstance(events, list):
        return []
    vertices = {node["id"] for node in graph.get("nodes", []) if isinstance(node, dict)}
    edge_weights: dict[tuple[str, str], list[float]] = {}
    for edge in graph.get("edges", []):
        try:
            weight = float(edge["weight"])
        except (KeyError, TypeError, ValueError):
            continue
        edge_weights.setdefault((str(edge["source"]), str(edge["target"])), []).append(weight)
    issues: list[str] = []
    allowed = {"select", "relax", "enqueue", "dequeue", "visit", "detect_negative_cycle", "complete"}
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            issues.append(f"events[{index}] must be an object")
            continue
        operation = event.get("operation")
        if operation not in allowed:
            issues.append(f"events[{index}] has unsupported operation {operation!r}")
            continue
        if operation == "relax":
            source, target = event.get("source"), event.get("target")
            if source is None or target is None:
                issues.append(f"events[{index}] relax requires source and target")
                continue
            if (str(source), str(target)) not in edge_weights:
                issues.append(f"events[{index}] relax references a non-existent edge")
                continue
            if event.get("weight") is not None:
                try:
                    weight = float(event["weight"])
                except (TypeError, ValueError):
                    issues.append(f"events[{index}] relax weight is not numeric")
                    continue
                if not any(math.isclose(weight, candidate, rel_tol=1e-9, abs_tol=1e-9) for candidate in edge_weights[(str(source), str(target))]):
                    issues.append(f"events[{index}] relax weight conflicts with graph")
            if algorithm == "dijkstra" and any(weight < 0 for weight in edge_weights[(str(source), str(target))]):
                issues.append(f"events[{index}] Dijkstra cannot relax a negative edge")
        if operation in {"select", "enqueue", "dequeue", "visit"}:
            vertex = event.get("target", event.get("source"))
            if vertex is not None and str(vertex) not in vertices:
                issues.append(f"events[{index}] references unknown vertex {vertex!r}")
    return issues


def compile_algorithm_trace(dsl: dict[str, Any]) -> dict[str, Any]:
    """Compile migrated algorithm frames and attach an auditable report."""
    if not isinstance(dsl, dict) or not isinstance(dsl.get("frames"), list):
        return dsl
    result = deepcopy(dsl)
    frames = result["frames"]
    algorithm = _algorithm(result.get("topic"), frames)
    if algorithm not in {"dijkstra", "bellman_ford", "bfs", "dfs"}:
        return result
    graph = _primary_graph(frames)
    report: dict[str, Any] = {
        "applied": False,
        "algorithm": algorithm,
        "mode": "deterministic_state_machine",
        "frames_compiled": 0,
        "event_frames": 0,
        "hint_aligned_frames": 0,
        "warnings": [],
        "issues": [],
    }
    if graph is None or not graph.get("edges"):
        report["issues"].append("primary graph with executable edges was not found")
        result["algorithm_trace_compilation"] = report
        return result
    source = _source(frames, graph)
    if source is None:
        report["issues"].append("source vertex was not found")
        result["algorithm_trace_compilation"] = report
        return result
    try:
        if algorithm == "dijkstra":
            states = simulate_dijkstra(graph, source)
        elif algorithm == "bellman_ford":
            states = simulate_bellman_ford(graph, source)
        elif algorithm == "bfs":
            states = simulate_bfs(graph, source)
        else:
            states = simulate_dfs(graph, source)
    except ValueError as exc:
        report["issues"].append(str(exc))
        result["algorithm_trace_compilation"] = report
        return result

    # A model may append an intermediate explanation after a summary frame
    # (the common ``f_003b`` pattern).  Once the executable graph is known,
    # order frames by their deterministic state-machine position.  This is a
    # presentation-order normalization; raw model frames remain in the audit
    # record and no state value is invented.
    if algorithm == "dijkstra":
        ranked: list[tuple[int, int, dict[str, Any]]] = []
        for index, frame in enumerate(frames):
            snapshot = frame.get("state_snapshot") if isinstance(frame, dict) else None
            expected = _state_for_frame(frame, snapshot, states, algorithm=algorithm) if isinstance(snapshot, dict) else None
            state_index = next((position for position, state in enumerate(states) if state == expected), len(states) + index)
            ranked.append((state_index, index, frame))
        ordered = [frame for _, _, frame in sorted(ranked, key=lambda item: (item[0], item[1]))]
        if ordered != frames:
            frames[:] = ordered
            report["frame_order_normalized"] = True

    for frame in frames:
        if not isinstance(frame, dict):
            continue
        snapshot = frame.get("state_snapshot")
        if not isinstance(snapshot, dict):
            continue
        # Secondary-only visuals are independent teaching examples.
        graphs = [visual for visual in frame.get("visual_objects", []) if isinstance(visual, dict) and visual.get("type") == "graph"]
        if graphs and not any(_graph_role(visual) == "primary" for visual in graphs):
            continue
        expected = _state_for_frame(frame, snapshot, states, algorithm=algorithm)
        if expected is None:
            # A non-executable explanatory frame (for example a comparison
            # or negative-cycle explanation) should not be forced into the
            # primary state machine.
            continue
        event_issues = _event_issues(snapshot, graph, algorithm=algorithm)
        if event_issues:
            report["issues"].extend({"frame_id": frame.get("frame_id"), "description": issue} for issue in event_issues)
            continue
        issues = _compatible_hint(snapshot, expected, algorithm=algorithm)
        # visited/queue are derived presentation hints.  The deterministic
        # simulator is authoritative and replaces these fields below; keep a
        # mismatch auditable as a warning instead of turning an otherwise valid
        # trace into a hard failure (e.g. a summary frame emitted after the
        # final dequeue).  Distances, predecessors and explicit events remain
        # hard semantic claims.
        soft_prefixes = ("visited conflicts", "processed conflicts", "queue order conflicts", "queue entries conflict")
        soft_issues = [issue for issue in issues if issue.startswith(soft_prefixes)]
        hard_issues = [issue for issue in issues if issue not in soft_issues]
        report["warnings"].extend(
            {"frame_id": frame.get("frame_id"), "description": issue}
            for issue in soft_issues
        )
        if hard_issues:
            report["issues"].extend({"frame_id": frame.get("frame_id"), "description": issue} for issue in hard_issues)
            continue
        frame["state_snapshot"] = _merge_expected(snapshot, expected)
        report["frames_compiled"] += 1
        if isinstance(snapshot.get("events"), list) and snapshot["events"]:
            report["event_frames"] += 1
        else:
            report["hint_aligned_frames"] += 1

    report["applied"] = report["frames_compiled"] > 0
    report["source"] = source
    report["state_count"] = len(states)
    result["algorithm_trace_compilation"] = report
    return result


__all__ = ["compile_algorithm_trace"]
