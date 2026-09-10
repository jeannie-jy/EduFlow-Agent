"""validate_dsl_schema & check_state_consistency Tools。

DSL 校验工具：确定性检查，不依赖 LLM。
"""

from __future__ import annotations

import logging
import math
import re
from copy import deepcopy
from typing import Any

logger = logging.getLogger(__name__)

_INFINITY_VALUES = {"∞", "inf", "+inf", "infinity", "无穷", "无穷大"}
_EMPTY_QUEUE_SENTINELS = {"", "[]", "empty", "none", "null", "空", "空队列"}
_SHORTEST_PATH_MARKERS = ("dijkstra", "shortest path", "最短路径")
_BELLMAN_FORD_MARKERS = ("bellman-ford", "bellman ford", "bellmanford", "bellman-ford", "bellman")
_SECONDARY_GRAPH_MARKERS = (
    "negative",
    "counterexample",
    "practice",
    "exercise",
    "反例",
    "练习",
    "负环",
)
_DERIVED_GRAPH_MARKERS = ("path_tree", "path-tree", "shortest_path_tree", "路径树")


def _distance_value(value: Any) -> float | None:
    """Convert the common DSL distance encodings to a comparable number."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(float(value)) else math.inf
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in _INFINITY_VALUES:
            return math.inf
        try:
            parsed = float(normalized)
        except ValueError:
            return None
        return parsed if math.isfinite(parsed) else math.inf
    return None


def _queue_values(value: Any) -> list[str]:
    """Extract vertex ids from queue/heap snapshots without assuming one format."""
    if isinstance(value, str):
        if value.strip().casefold() in _EMPTY_QUEUE_SENTINELS:
            return []
        return [match for match in re.findall(r"([A-Za-z0-9_\-]+)\s*(?:\([^)]*\))?", value)]
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, dict):
            candidate = item.get("id", item.get("vertex", item.get("node", item.get("key"))))
        else:
            candidate = item
        if candidate is not None:
            text = str(candidate).strip()
            if text:
                result.append(text.split("(", 1)[0].strip())
    return result


def _negative_counterexample_issues(frame: dict[str, Any]) -> list[str]:
    """Validate an explicit Dijkstra trace on a secondary negative-edge graph.

    A counterexample may intentionally produce a wrong shortest-path result,
    but it must still execute Dijkstra faithfully: extract the smallest current
    tentative distance, relax outgoing edges, and only then demonstrate how a
    later negative edge would improve an already-settled vertex.
    """
    snapshot = frame.get("state_snapshot", {})
    if not isinstance(snapshot, dict):
        return []
    explicitly_wrong_trace = "visited_wrong" in snapshot or "wrong_dist" in snapshot
    if (
        any(_graph_role(graph) == "primary" for graph in _graph_visuals(frame))
        and not explicitly_wrong_trace
        and not _frame_state_likely_secondary(frame)
    ):
        # In a mixed comparison frame, ordinary ``visited``/``dist`` belongs
        # to the primary graph.  Only explicitly named wrong-trace fields may
        # be evaluated against the secondary counterexample.
        return []
    raw_visited = snapshot.get("visited_wrong", snapshot.get("visited"))
    raw_dist = snapshot.get("wrong_dist", snapshot.get("dist"))
    if not isinstance(raw_visited, list) or not isinstance(raw_dist, dict):
        return []

    visited = [str(vertex) for vertex in raw_visited]
    claimed_dist = {
        str(vertex): distance
        for vertex, value in raw_dist.items()
        if (distance := _distance_value(value)) is not None
    }
    if not visited or not claimed_dist:
        return []

    issues: list[str] = []
    for graph in _graph_visuals(frame):
        if _graph_role(graph) != "secondary":
            continue
        raw_edges = graph.get("edges", graph.get("graph_edges", []))
        if not isinstance(raw_edges, list):
            continue
        edges: list[tuple[str, str, float]] = []
        vertices = {
            str(node.get("id", node.get("label")))
            for node in graph.get("nodes", [])
            if isinstance(node, dict)
            and node.get("id", node.get("label")) is not None
        }
        for edge in raw_edges:
            if not isinstance(edge, dict):
                continue
            source, target = edge.get("source"), edge.get("target")
            weight = _distance_value(edge.get("weight"))
            if (
                source is None
                or target is None
                or weight is None
                or not math.isfinite(weight)
            ):
                continue
            source_id, target_id = str(source), str(target)
            vertices.update((source_id, target_id))
            edges.append((source_id, target_id, weight))
            if not bool(graph.get("directed", False)):
                edges.append((target_id, source_id, weight))
        if not edges or not any(weight < 0 for _, _, weight in edges):
            continue

        source = visited[0]
        tentative = {vertex: math.inf for vertex in vertices}
        tentative[source] = 0.0
        settled: set[str] = set()
        trace_invalid = False
        for vertex in visited:
            if vertex not in tentative or vertex in settled:
                issues.append(f"负权反例的 visited 顺序包含无效或重复顶点 {vertex}")
                trace_invalid = True
                break
            unsettled_finite = {
                candidate: distance
                for candidate, distance in tentative.items()
                if candidate not in settled and math.isfinite(distance)
            }
            minimum = min(unsettled_finite.values()) if unsettled_finite else math.inf
            if tentative[vertex] > minimum + 1e-9:
                smaller = sorted(
                    candidate
                    for candidate, distance in unsettled_finite.items()
                    if abs(distance - minimum) <= 1e-9
                )
                issues.append(
                    f"负权反例未按当前最小距离选择顶点: 选择 {vertex}，"
                    f"应先选择 {smaller}"
                )
                trace_invalid = True
                break
            settled.add(vertex)
            for edge_source, target, weight in edges:
                if edge_source != vertex or target in settled:
                    continue
                tentative[target] = min(tentative[target], tentative[vertex] + weight)

        if trace_invalid:
            continue
        mismatches = sorted(
            vertex
            for vertex in set(claimed_dist) & set(tentative)
            if (
                math.isinf(claimed_dist[vertex]) != math.isinf(tentative[vertex])
                or (
                    math.isfinite(claimed_dist[vertex])
                    and abs(claimed_dist[vertex] - tentative[vertex]) > 1e-9
                )
            )
        )
        if mismatches:
            issues.append(
                "负权反例的 Dijkstra 状态未执行必要松弛: "
                f"距离不一致顶点 {mismatches}"
            )
    return issues


def _graph_edges(frames: list[dict[str, Any]]) -> tuple[set[str], list[dict[str, Any]]]:
    """Collect the first explicit graph definition used by the frames."""
    vertices: set[str] = set()
    edges: list[dict[str, Any]] = []
    for frame in frames:
        for visual in frame.get("visual_objects", []):
            if not isinstance(visual, dict):
                continue
            if visual.get("type") == "graph" and _graph_role(visual) == "primary":
                for node in visual.get("nodes", []):
                    if isinstance(node, dict):
                        node_id = node.get("id", node.get("label"))
                        if node_id is not None:
                            vertices.add(str(node_id))
                candidates = visual.get("edges", visual.get("graph_edges", []))
                if isinstance(candidates, list):
                    edges.extend(item for item in candidates if isinstance(item, dict))
            elif visual.get("type") == "edge":
                edges.append(visual)
        graph_state = frame.get("state_snapshot", {}).get("graph", {})
        if isinstance(graph_state, dict):
            for node in graph_state.get("vertices", graph_state.get("nodes", [])):
                if isinstance(node, dict):
                    node = node.get("id", node.get("label"))
                if node is not None:
                    vertices.add(str(node))
            state_edges = graph_state.get("edges", graph_state.get("graph_edges", []))
            if isinstance(state_edges, list):
                edges.extend(item for item in state_edges if isinstance(item, dict))
        if vertices and edges:
            break
    return vertices, edges


def _graph_visuals(frame: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        visual
        for visual in frame.get("visual_objects", [])
        if isinstance(visual, dict) and visual.get("type") == "graph"
    ]


def _graph_role(visual: dict[str, Any]) -> str:
    """Return the declared or inferred role of a graph visual.

    A teaching artifact can contain a primary execution graph and independent
    views such as a shortest-path tree, a negative-edge counterexample, or a
    practice graph.  Treating all of them as one mutable graph creates false
    invariant failures.  ``graph_role``/``role`` is preferred; legacy output
    is classified from the visual id and label.
    """
    declared = visual.get("graph_role", visual.get("role"))
    if isinstance(declared, str):
        normalized = declared.strip().casefold().replace("-", "_")
        if normalized in {"primary", "state", "main"}:
            return "primary"
        if normalized in {"derived", "path_tree", "view"}:
            return "derived"
        if normalized in {"secondary", "counterexample", "practice", "exercise", "example"}:
            return "secondary"

    identity = " ".join(
        str(visual.get(key, "")) for key in ("id", "label", "title")
    ).casefold()
    if any(marker in identity for marker in _DERIVED_GRAPH_MARKERS):
        return "derived"
    if any(marker in identity for marker in _SECONDARY_GRAPH_MARKERS):
        return "secondary"
    return "primary"


def _primary_graph_id(frames: list[dict[str, Any]]) -> str | None:
    """Find the stable primary graph id, if the artifact declares one."""
    for frame in frames:
        for visual in _graph_visuals(frame):
            if _graph_role(visual) == "primary" and visual.get("id"):
                return str(visual["id"])
    return None


def _frame_has_secondary_graph(frame: dict[str, Any]) -> bool:
    return any(_graph_role(visual) == "secondary" for visual in _graph_visuals(frame))


def _frame_has_primary_graph(frame: dict[str, Any], primary_graph_id: str | None) -> bool:
    for visual in _graph_visuals(frame):
        if _graph_role(visual) != "primary":
            continue
        if primary_graph_id is None or str(visual.get("id")) == primary_graph_id:
            return True
    return False


def _graph_vertices(visual: dict[str, Any]) -> set[str]:
    """Return vertex ids declared by one graph visual."""
    vertices: set[str] = set()
    for node in visual.get("nodes", []):
        if isinstance(node, dict):
            node_id = node.get("id", node.get("label"))
            if node_id is not None:
                vertices.add(str(node_id))
    for edge in visual.get("edges", visual.get("graph_edges", [])):
        if not isinstance(edge, dict):
            continue
        if edge.get("source") is not None:
            vertices.add(str(edge["source"]))
        if edge.get("target") is not None:
            vertices.add(str(edge["target"]))
    return vertices


def _graph_has_negative_edge(visual: dict[str, Any]) -> bool:
    for edge in visual.get("edges", visual.get("graph_edges", [])):
        if not isinstance(edge, dict):
            continue
        weight = _distance_value(edge.get("weight"))
        if weight is not None and math.isfinite(weight) and weight < 0:
            return True
    return False


def _state_distance_map(frame: dict[str, Any]) -> dict[str, Any] | None:
    snapshot = frame.get("state_snapshot", {})
    if not isinstance(snapshot, dict):
        return None
    for key in ("dist", "distances", "distance"):
        value = snapshot.get(key)
        if isinstance(value, dict):
            return value
    return None


def _frame_state_likely_secondary(frame: dict[str, Any]) -> bool:
    """Detect a secondary trace embedded beside the primary graph.

    Models frequently render both graphs in one frame but put the secondary
    graph's ordinary ``dist``/``visited`` fields in the top-level snapshot.
    When the snapshot vertex set exactly matches a negative graph and omits a
    vertex from the primary graph, it cannot be the primary execution state.
    This inference is deliberately narrow so ordinary mixed comparison frames
    remain part of the primary trace.
    """
    distance_map = _state_distance_map(frame)
    snapshot = frame.get("state_snapshot", {})
    if not isinstance(distance_map, dict) or not isinstance(snapshot, dict):
        return False
    secondary_graphs = [
        graph
        for graph in _graph_visuals(frame)
        if _graph_role(graph) == "secondary" and _graph_has_negative_edge(graph)
    ]
    if not secondary_graphs:
        return False
    state_vertices = {str(vertex) for vertex in distance_map}
    primary_vertices: set[str] = set()
    for graph in _graph_visuals(frame):
        if _graph_role(graph) == "primary":
            primary_vertices.update(_graph_vertices(graph))
    for graph in secondary_graphs:
        secondary_vertices = _graph_vertices(graph)
        if secondary_vertices and state_vertices == secondary_vertices:
            return True
    # A negative trace may expose only a subset of its graph, but an explicit
    # negative-only state must still not reset the primary baseline.
    if primary_vertices and state_vertices and state_vertices < primary_vertices:
        return any(
            key in snapshot
            for key in ("negative_edge", "dijkstra_result", "wrong_dist", "neg_dist")
        )
    return False


def _topic_requests_negative_counterexample(topic_text: str) -> bool:
    markers = (
        "负权反例",
        "负权边反例",
        "反例",
        "counterexample",
        "negative edge example",
    )
    return any(marker in topic_text for marker in markers)


def _strip_unrequested_negative_examples(
    frames: list[dict[str, Any]],
    *,
    topic_text: str,
) -> list[dict[str, Any]]:
    """Remove invalid illustrative negative graphs when the topic did not ask for one.

    The primary lesson remains intact, while a model's optional counterexample
    cannot poison the executable Dijkstra trace. Explicit counterexample topics
    are never modified and continue to be checked strictly.
    """
    if _topic_requests_negative_counterexample(topic_text):
        return frames

    cleaned: list[dict[str, Any]] = []
    for frame in frames:
        if not isinstance(frame, dict):
            cleaned.append(frame)
            continue
        negative_graphs = [
            visual
            for visual in _graph_visuals(frame)
            if _graph_has_negative_edge(visual)
        ]
        if not negative_graphs:
            cleaned.append(frame)
            continue

        secondary_state = _frame_state_likely_secondary(frame)
        has_safe_primary = any(
            _graph_role(visual) == "primary" and not _graph_has_negative_edge(visual)
            for visual in _graph_visuals(frame)
        )
        has_negative_primary = any(
            _graph_role(visual) == "primary" and _graph_has_negative_edge(visual)
            for visual in negative_graphs
        )
        # If the frame only contains a negative primary graph, it is an
        # unrequested counterexample rather than a valid execution step. Drop
        # it instead of relabelling a negative trace as the main algorithm.
        if has_negative_primary and not has_safe_primary:
            continue

        state = frame.get("state_snapshot")
        if not isinstance(state, dict):
            state = {}
            frame["state_snapshot"] = state
        frame["visual_objects"] = [
            visual
            for visual in frame.get("visual_objects", [])
            if not (
                isinstance(visual, dict)
                and visual.get("type") == "graph"
                and visual in negative_graphs
            )
        ]

        # Mixed frames may carry a correctly named primary snapshot alongside
        # the negative trace. Preserve the primary state and discard only the
        # counterexample fields.
        primary_dist = state.get("primary_dist")
        primary_visited = state.get("primary_visited")
        if isinstance(primary_dist, dict) and not isinstance(state.get("dist"), dict):
            state["dist"] = deepcopy(primary_dist)
        if isinstance(primary_visited, list) and not isinstance(state.get("visited"), list):
            state["visited"] = deepcopy(primary_visited)
        if secondary_state and not isinstance(primary_dist, dict):
            for key in ("dist", "distances", "distance", "visited", "processed"):
                state.pop(key, None)
        for key in list(state):
            normalized = str(key).casefold()
            if (
                normalized.startswith(("neg_", "negative_", "wrong_"))
                or normalized in {
                    "primary_dist",
                    "primary_visited",
                    "visited_wrong",
                    "dijkstra_result",
                    "true_result",
                    "error_step",
                    "negative_edge",
                }
            ):
                state.pop(key, None)

        # A frame that only described the discarded counterexample carries no
        # executable primary state; dropping it is safer than relabelling a
        # wrong trace as the main algorithm.
        if (
            secondary_state
            or (
                not isinstance(state.get("dist"), dict)
                and not isinstance(state.get("distances"), dict)
                and not isinstance(state.get("distance"), dict)
                and not isinstance(state.get("visited"), list)
                and not isinstance(state.get("processed"), list)
            )
        ):
            continue
        cleaned.append(frame)
    return cleaned


def _stabilize_primary_graph_topology(
    frames: list[dict[str, Any]],
    *,
    topic_text: str,
) -> int:
    """Keep a Dijkstra primary graph immutable across execution frames."""
    if _topic_requests_negative_counterexample(topic_text):
        return 0
    baseline: dict[str, Any] | None = None
    baseline_signature: frozenset[tuple[str, str, str]] | None = None
    repairs = 0
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        for visual in _graph_visuals(frame):
            if _graph_role(visual) != "primary" or _graph_has_negative_edge(visual):
                continue
            signature = _frame_graph_signature(
                {"visual_objects": [visual]},
                primary_graph_id=None,
            )
            if baseline is None:
                baseline = deepcopy(visual)
                baseline_signature = signature
                continue
            if signature == baseline_signature:
                continue
            # Preserve frame-local styling/labels but restore the executable
            # topology (nodes and edges) to the first valid primary graph.
            visual["nodes"] = deepcopy(baseline.get("nodes", []))
            visual["edges"] = deepcopy(baseline.get("edges", []))
            repairs += 1
    return repairs


def _repair_shortest_path_trees(frames: list[dict[str, Any]]) -> int:
    """Rebuild explicit path-tree visuals from the frame's predecessor map.

    A model may leave an examined-but-not-selected edge (for example ``B->C``)
    in the final tree even though ``prev[C]`` is ``A``.  The predecessor map
    and distance snapshot are the executable source of truth, so derived tree
    visuals are normalized to that single parent per vertex.
    """
    _, edges = _graph_edges(frames)
    weights: dict[tuple[str, str], list[float]] = {}
    for edge in edges:
        source, target = edge.get("source"), edge.get("target")
        weight = _distance_value(edge.get("weight"))
        if source is not None and target is not None and weight is not None and math.isfinite(weight):
            weights.setdefault((str(source), str(target)), []).append(weight)
    if not weights:
        return 0
    repairs = 0
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        snapshot = frame.get("state_snapshot")
        if not isinstance(snapshot, dict):
            continue
        tree_keys = [key for key in ("shortest_path_tree", "path_tree") if key in snapshot]
        derived_visuals = [
            visual
            for visual in _graph_visuals(frame)
            if _graph_role(visual) == "derived"
            and any(marker in " ".join(str(visual.get(key, "")) for key in ("id", "label", "title")).casefold() for marker in _DERIVED_GRAPH_MARKERS)
        ]
        if not tree_keys and not derived_visuals:
            continue

        raw_dist = snapshot.get("dist", snapshot.get("distances", snapshot.get("distance")))
        distances = {
            str(vertex): value
            for vertex, raw_value in raw_dist.items()
            if (value := _distance_value(raw_value)) is not None
        } if isinstance(raw_dist, dict) else {}
        raw_prev = snapshot.get("prev", snapshot.get("predecessors", {}))
        candidates: list[tuple[str, str, float]] = []
        if isinstance(raw_prev, dict):
            for child, parent in raw_prev.items():
                if parent is None:
                    continue
                parent_text, child_text = str(parent), str(child)
                for weight in weights.get((parent_text, child_text), []):
                    parent_dist = distances.get(parent_text)
                    child_dist = distances.get(child_text)
                    if parent_dist is None or child_dist is None or (
                        math.isfinite(parent_dist)
                        and math.isfinite(child_dist)
                        and math.isclose(child_dist, parent_dist + weight, abs_tol=1e-9)
                    ):
                        candidates.append((parent_text, child_text, weight))
                        break
        if not candidates and distances:
            for (parent_text, child_text), edge_weights in weights.items():
                parent_dist = distances.get(parent_text)
                child_dist = distances.get(child_text)
                if parent_dist is None or child_dist is None or not math.isfinite(parent_dist) or not math.isfinite(child_dist):
                    continue
                if math.isclose(child_dist, parent_dist + edge_weights[0], abs_tol=1e-9):
                    candidates.append((parent_text, child_text, edge_weights[0]))
        # Preserve one deterministic parent per child.
        desired: list[dict[str, Any]] = []
        seen_children: set[str] = set()
        for parent_text, child_text, weight in candidates:
            if child_text in seen_children:
                continue
            seen_children.add(child_text)
            desired.append({"source": parent_text, "target": child_text, "weight": int(weight) if weight.is_integer() else weight})

        if not desired and not candidates:
            # Do not erase an intentionally empty/partially specified tree when
            # the snapshot provides insufficient evidence to reconstruct it.
            continue

        for key in tree_keys:
            if snapshot.get(key) != desired:
                snapshot[key] = deepcopy(desired)
                repairs += 1
        for visual in derived_visuals:
            if visual.get("edges") != desired:
                visual["edges"] = deepcopy(desired)
                repairs += 1
    return repairs


def _bellman_frame_is_illustrative(frame: dict[str, Any]) -> bool:
    """Identify a Dijkstra comparison frame in a Bellman-Ford lesson."""
    snapshot = frame.get("state_snapshot", {})
    if isinstance(snapshot, dict) and snapshot.get("phase") == "dijkstra_failure_demo":
        return True
    identity = " ".join(
        str(frame.get(key, "")) for key in ("title", "narration")
    ).casefold()
    return "dijkstra" in identity and "bellman" not in identity


def _bellman_primary_graph(frames: list[dict[str, Any]]) -> tuple[list[str], list[tuple[str, str, float]]]:
    """Extract the main Bellman-Ford teaching graph, not comparison examples."""
    candidates: list[tuple[int, list[str], list[tuple[str, str, float]]]] = []
    for frame in frames:
        if not isinstance(frame, dict) or _bellman_frame_is_illustrative(frame):
            continue
        for visual in _graph_visuals(frame):
            if _graph_role(visual) != "primary":
                continue
            vertices = list(_graph_vertices(visual))
            edges: list[tuple[str, str, float]] = []
            for edge in visual.get("edges", visual.get("graph_edges", [])):
                if not isinstance(edge, dict):
                    continue
                source, target = edge.get("source"), edge.get("target")
                weight = _distance_value(edge.get("weight"))
                if source is None or target is None or weight is None or math.isinf(weight):
                    continue
                edges.append((str(source), str(target), weight))
            if vertices and edges:
                identity = " ".join(str(visual.get(key, "")) for key in ("id", "label", "title")).casefold()
                score = 2 if "bellman" in identity else 0
                if isinstance(frame.get("state_snapshot"), dict) and "round" in frame["state_snapshot"]:
                    score += 1
                candidates.append((score, sorted(set(vertices)), edges))
    if not candidates:
        return [], []
    _, vertices, edges = max(candidates, key=lambda item: item[0])
    return vertices, edges


def _bellman_pass_states(
    vertices: list[str],
    edges: list[tuple[str, str, float]],
    source: str,
) -> list[dict[str, float]]:
    """Compute deterministic in-place Bellman-Ford states by relaxation round."""
    distances = {vertex: math.inf for vertex in vertices}
    distances[source] = 0.0
    states = [dict(distances)]
    for _ in range(max(0, len(vertices) - 1)):
        for left, right, weight in edges:
            if math.isfinite(distances.get(left, math.inf)):
                candidate = distances[left] + weight
                if candidate < distances.get(right, math.inf):
                    distances[right] = candidate
        states.append(dict(distances))
    return states


def _encode_distance(value: float, original: Any) -> Any:
    """Preserve the artifact's infinity representation while repairing numbers."""
    if math.isinf(value):
        return original if isinstance(original, str) else "∞"
    if isinstance(original, int) and not isinstance(original, bool):
        return int(value) if float(value).is_integer() else value
    return int(value) if float(value).is_integer() else value


def _repair_bellman_text(value: str, states: list[dict[str, float]]) -> str:
    """Correct explicit ``第 k 轮 ... dist[x]=y`` claims in model prose."""
    if not isinstance(value, str) or not states:
        return value
    repaired = value
    for round_index, expected in enumerate(states):
        if round_index == 0:
            round_pattern = r"初始"
        else:
            round_pattern = rf"第\s*{round_index}\s*轮"
        match = re.search(round_pattern, repaired)
        if not match:
            continue
        end_match = re.search(r"[；;。！？!?\n]", repaired[match.end():])
        end = match.end() + end_match.start() if end_match else len(repaired)
        clause = repaired[match.start():end]
        for vertex, distance in expected.items():
            number = "∞" if math.isinf(distance) else (str(int(distance)) if distance.is_integer() else str(distance))
            token = re.compile(
                rf"(dist\s*\[\s*{re.escape(vertex)}\s*\]\s*=\s*)(-?\d+(?:\.\d+)?|∞|inf|无穷(?:大)?)",
                flags=re.IGNORECASE,
            )
            clause = token.sub(rf"\g<1>{number}", clause)
        repaired = repaired[:match.start()] + clause + repaired[end:]
    return repaired


def _stabilize_bellman_ford_trace(frames: list[dict[str, Any]]) -> int:
    """Repair Bellman-Ford snapshots/tables against the declared graph.

    LLMs often mix in-place and synchronous relaxation when narrating a round.
    The graph and round number are already structured data, so recomputing the
    expected state is deterministic and avoids spending another LLM request.
    """
    vertices, edges = _bellman_primary_graph(frames)
    if not vertices or not edges:
        return 0
    source = None
    for frame in frames:
        snapshot = frame.get("state_snapshot", {}) if isinstance(frame, dict) else {}
        raw_dist = snapshot.get("dist", snapshot.get("distances")) if isinstance(snapshot, dict) else None
        if isinstance(raw_dist, dict):
            for vertex, raw_value in raw_dist.items():
                if _distance_value(raw_value) == 0:
                    source = str(vertex)
                    break
        if source:
            break
    source = source or vertices[0]
    states = _bellman_pass_states(vertices, edges, source)
    repairs = 0
    secondary_active = False
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        if _bellman_frame_is_illustrative(frame):
            continue
        has_secondary = _frame_has_secondary_graph(frame)
        # Bellman-Ford lesson plans often redraw the same teaching graph with
        # a new visual id in each frame. Unlike Dijkstra's immutable id
        # contract, accept any non-secondary primary graph here.
        has_primary = any(_graph_role(visual) == "primary" for visual in _graph_visuals(frame))
        if has_secondary and not has_primary:
            secondary_active = True
            continue
        if secondary_active and not has_primary:
            continue
        if has_primary:
            secondary_active = False
        snapshot = frame.get("state_snapshot")
        if not isinstance(snapshot, dict):
            continue
        round_value = snapshot.get("round", snapshot.get("iteration"))
        try:
            round_index = max(0, min(int(round_value), len(states) - 1))
        except (TypeError, ValueError):
            round_index = None
        expected = states[round_index] if round_index is not None else None
        if expected is not None:
            key = "dist" if isinstance(snapshot.get("dist"), dict) else "distances" if isinstance(snapshot.get("distances"), dict) else None
            if key:
                raw_dist = snapshot[key]
                for vertex, distance in expected.items():
                    original = raw_dist.get(vertex, raw_dist.get(str(vertex)))
                    if original is None:
                        continue
                    repaired = _encode_distance(distance, original)
                    if raw_dist.get(vertex, raw_dist.get(str(vertex))) != repaired:
                        raw_dist[vertex] = repaired
                        repairs += 1

            for visual in frame.get("visual_objects", []):
                if not isinstance(visual, dict) or visual.get("type") != "table":
                    continue
                headers = visual.get("headers", visual.get("columns", []))
                rows = visual.get("rows")
                if not isinstance(headers, list) or not isinstance(rows, list):
                    continue
                header_index = {str(header): index for index, header in enumerate(headers)}
                for row in rows:
                    if not isinstance(row, list):
                        continue
                    label = str(row[0]) if row else ""
                    round_match = re.search(r"(?:第\s*)?(\d+)\s*轮", label)
                    if not round_match:
                        continue
                    row_round = max(0, min(int(round_match.group(1)), len(states) - 1))
                    for vertex, distance in states[row_round].items():
                        index = header_index.get(vertex)
                        if index is None or index >= len(row):
                            continue
                        repaired = _encode_distance(distance, row[index])
                        if row[index] != repaired:
                            row[index] = repaired
                            repairs += 1

        def repair(value: Any) -> Any:
            if isinstance(value, str):
                return _repair_bellman_text(value, states)
            if isinstance(value, list):
                return [repair(item) for item in value]
            if isinstance(value, dict):
                return {key: repair(item) for key, item in value.items()}
            return value

        repaired_frame = repair(frame)
        if repaired_frame != frame:
            frame.clear()
            frame.update(repaired_frame)
            repairs += 1
    return repairs


def _bellman_ford_invariant_issues(frames: list[dict[str, Any]]) -> list[str]:
    """Check structured Bellman-Ford distances against graph relaxation rounds."""
    vertices, edges = _bellman_primary_graph(frames)
    if not vertices or not edges:
        return []
    source = None
    for frame in frames:
        snapshot = frame.get("state_snapshot", {}) if isinstance(frame, dict) else {}
        raw_dist = snapshot.get("dist", snapshot.get("distances")) if isinstance(snapshot, dict) else None
        if isinstance(raw_dist, dict):
            source = next(
                (str(vertex) for vertex, value in raw_dist.items() if _distance_value(value) == 0),
                None,
            )
        if source:
            break
    states = _bellman_pass_states(vertices, edges, source or vertices[0])
    issues: list[str] = []
    secondary_active = False
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        if _bellman_frame_is_illustrative(frame):
            continue
        has_secondary = _frame_has_secondary_graph(frame)
        has_primary = any(_graph_role(visual) == "primary" for visual in _graph_visuals(frame))
        if has_secondary and not has_primary:
            secondary_active = True
            continue
        if secondary_active and not has_primary:
            continue
        if has_primary:
            secondary_active = False
        snapshot = frame.get("state_snapshot")
        if not isinstance(snapshot, dict):
            continue
        raw_dist = snapshot.get("dist", snapshot.get("distances"))
        if not isinstance(raw_dist, dict):
            continue
        try:
            round_index = max(0, min(int(snapshot.get("round", snapshot.get("iteration", 0))), len(states) - 1))
        except (TypeError, ValueError):
            continue
        expected = states[round_index]
        for vertex, distance in expected.items():
            actual = _distance_value(raw_dist.get(vertex, raw_dist.get(str(vertex))))
            if actual is None:
                continue
            if (math.isinf(distance) and not math.isinf(actual)) or (
                not math.isinf(distance) and (math.isinf(actual) or abs(actual - distance) > 1e-9)
            ):
                issues.append(
                    f"Bellman-Ford 第 {round_index} 轮 dist[{vertex}]={actual:g}，"
                    f"按图和边遍历顺序应为 {('∞' if math.isinf(distance) else f'{distance:g}')}"
                )
    return issues


def _frame_graph_signature(
    frame: dict[str, Any],
    *,
    primary_graph_id: str | None = None,
) -> frozenset[tuple[str, str, str]]:
    """Return the primary graph edge signature for one frame.

    Derived and secondary graphs are intentionally excluded.  The primary
    graph is selected by its declared role or stable visual id; this keeps the
    invariant focused on the execution trace rather than every illustration.
    """
    raw_edges: list[dict[str, Any]] = []
    for visual in _graph_visuals(frame):
        if _graph_role(visual) != "primary":
            continue
        if primary_graph_id and str(visual.get("id")) != primary_graph_id:
            continue
        candidates = visual.get("edges", visual.get("graph_edges", []))
        if isinstance(candidates, list):
            raw_edges.extend(item for item in candidates if isinstance(item, dict))
    if not _frame_has_secondary_graph(frame):
        for visual in frame.get("visual_objects", []):
            if isinstance(visual, dict) and visual.get("type") == "edge":
                raw_edges.append(visual)
        graph_state = frame.get("state_snapshot", {}).get("graph", {})
        if isinstance(graph_state, dict):
            candidates = graph_state.get("edges", graph_state.get("graph_edges", []))
            if isinstance(candidates, list):
                raw_edges.extend(item for item in candidates if isinstance(item, dict))
    return frozenset(
        (
            str(edge.get("source")),
            str(edge.get("target")),
            (
                "" if edge.get("weight") is None
                else f"{weight:g}" if (weight := _distance_value(edge.get("weight"))) is not None
                else str(edge.get("weight"))
            ),
        )
        for edge in raw_edges
        if edge.get("source") is not None and edge.get("target") is not None
    )


def _extract_tree_edges(value: Any) -> list[tuple[str, str]]:
    """Read shortest-path tree/predecessor encodings emitted by the model."""
    if isinstance(value, dict):
        result: list[tuple[str, str]] = []
        for child, parent in value.items():
            if isinstance(parent, str):
                result.append((parent, str(child)))
        return result
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if isinstance(item, str) and "-" in item:
            parent, child = item.split("-", 1)
            if parent.strip() and child.strip():
                result.append((parent.strip(), child.strip()))
        elif isinstance(item, dict):
            parent = item.get("source", item.get("parent", item.get("from")))
            child = item.get("target", item.get("child", item.get("to")))
            if parent is not None and child is not None:
                result.append((str(parent), str(child)))
    return result


def stabilize_algorithm_trace(dsl: dict[str, Any]) -> dict[str, Any]:
    """Apply deterministic, semantics-preserving guards to model state traces.

    Dijkstra's ``visited`` set is monotonic on the primary execution trace and
    a vertex whose distance is explicitly infinite is unreachable from the
    source, so it must not be presented as settled.  These two facts let us
    repair common model drift without another LLM call.  Secondary/practice
    graphs are kept independent and never replace the primary trace baseline.
    """
    if not isinstance(dsl, dict):
        return {}
    result = deepcopy(dsl)
    topic_text = str(result.get("topic", "")).casefold()
    frames = result.get("frames", [])
    if not isinstance(frames, list):
        return result
    if any(marker in topic_text for marker in _BELLMAN_FORD_MARKERS):
        bellman_repairs = _stabilize_bellman_ford_trace(frames)
        if bellman_repairs:
            logger.info("Algorithm guardrail stabilized Bellman-Ford trace | repairs=%d", bellman_repairs)
    if not any(marker in topic_text for marker in _SHORTEST_PATH_MARKERS):
        result["frames"] = frames
        return result
    frames = _strip_unrequested_negative_examples(frames, topic_text=topic_text)
    result["frames"] = frames
    tree_repairs = _repair_shortest_path_trees(frames)
    if tree_repairs:
        logger.info("Algorithm guardrail stabilized shortest-path tree | repairs=%d", tree_repairs)
    repairs = _stabilize_primary_graph_topology(frames, topic_text=topic_text)
    primary_graph_id = _primary_graph_id(frames)
    previous_visited: list[Any] = []
    previous_dist: dict[str, float] = {}
    secondary_trace_active = False

    for frame in frames:
        if not isinstance(frame, dict):
            continue
        has_secondary = _frame_has_secondary_graph(frame)
        state_is_secondary = _frame_state_likely_secondary(frame)
        has_primary = _frame_has_primary_graph(frame, primary_graph_id) and not state_is_secondary
        # A mixed comparison frame can show a secondary graph beside the
        # primary graph.  Its state snapshot still belongs to the explicitly
        # present primary trace; only a secondary-only frame starts an
        # independent trace.
        if has_secondary and not has_primary:
            secondary_trace_active = True
            continue
        if secondary_trace_active and not has_primary:
            continue
        if has_primary:
            secondary_trace_active = False

        snapshot = frame.get("state_snapshot")
        if not isinstance(snapshot, dict):
            continue
        raw_dist = snapshot.get(
            "dist", snapshot.get("distances", snapshot.get("distance"))
        )
        distances = {
            str(vertex): distance
            for vertex, value in raw_dist.items()
            if (distance := _distance_value(value)) is not None
        } if isinstance(raw_dist, dict) else {}
        if isinstance(raw_dist, dict) and previous_dist:
            for key, value in list(raw_dist.items()):
                current = _distance_value(value)
                before = previous_dist.get(str(key))
                if (
                    current is not None
                    and before is not None
                    and math.isfinite(before)
                    and (
                        (math.isfinite(current) and current > before + 1e-9)
                        or math.isinf(current)
                    )
                ):
                    raw_dist[key] = before
                    distances[str(key)] = before
                    repairs += 1
        if distances:
            previous_dist = {
                **previous_dist,
                **distances,
            }
        visited_key = (
            "visited"
            if isinstance(snapshot.get("visited"), list)
            else "processed"
            if isinstance(snapshot.get("processed"), list)
            else None
        )
        if visited_key is None:
            continue

        current: list[Any] = []
        current_ids: set[str] = set()
        for vertex in snapshot[visited_key]:
            vertex_id = str(vertex)
            distance = distances.get(vertex_id)
            if distance is not None and math.isinf(distance):
                repairs += 1
                continue
            if vertex_id not in current_ids:
                current.append(vertex)
                current_ids.add(vertex_id)

        stabilized: list[Any] = []
        stabilized_ids: set[str] = set()
        for vertex in [*previous_visited, *current]:
            vertex_id = str(vertex)
            distance = distances.get(vertex_id)
            if distance is not None and math.isinf(distance):
                continue
            if vertex_id not in stabilized_ids:
                stabilized.append(vertex)
                stabilized_ids.add(vertex_id)

        if stabilized != snapshot[visited_key]:
            snapshot[visited_key] = stabilized
            repairs += 1
        previous_visited = stabilized

    if repairs:
        logger.info("Algorithm guardrail stabilized Dijkstra trace | repairs=%d", repairs)
    return result


async def check_algorithm_invariants(
    frames: list[dict[str, Any]],
    *,
    topic: str = "",
) -> dict[str, Any]:
    """Check graph-algorithm invariants that generic state checks cannot prove.

    The check is intentionally scoped to Dijkstra/shortest-path artifacts. It
    validates only evidence explicitly present in the DSL, so unrelated graph
    lessons are not rejected merely because they use different state shapes.
    """
    topic_text = str(topic).casefold()
    bellman_requested = any(marker in topic_text for marker in _BELLMAN_FORD_MARKERS)
    shortest_path_requested = any(marker in topic_text for marker in _SHORTEST_PATH_MARKERS)
    if not shortest_path_requested and not bellman_requested:
        return {"checked": False, "consistent": True, "issues": []}

    issues: list[dict[str, Any]] = []
    if bellman_requested:
        issues.extend(
            {"frame_id": "?", "description": description}
            for description in _bellman_ford_invariant_issues(frames)
        )
    vertices, edges = _graph_edges(frames)
    edge_map: dict[tuple[str, str], list[float]] = {}
    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        if source is None or target is None:
            continue
        source_text, target_text = str(source), str(target)
        vertices.update((source_text, target_text))
        weight = _distance_value(edge.get("weight"))
        if weight is not None and math.isfinite(weight):
            edge_map.setdefault((source_text, target_text), []).append(weight)
            if "dijkstra" in topic_text and weight < 0:
                issues.append({
                    "frame_id": "?",
                    "description": f"Dijkstra 图中存在负权边 {source_text}->{target_text}",
                })

    previous_dist: dict[str, float] | None = None
    previous_visited: set[str] | None = None
    previous_queue: list[str] | None = None
    graph_signature: frozenset[tuple[str, str, str]] | None = None
    primary_graph_id = _primary_graph_id(frames)
    final_dist: dict[str, float] = {}
    # A frame may expose the same path tree both as a derived graph and in its
    # state snapshot. Later frames may repeat an unchanged tree. Keep evidence
    # scoped to each frame so those representations are not mistaken for
    # multiple predecessors.
    tree_edges_by_frame: dict[str, set[tuple[str, str]]] = {}
    secondary_trace_active = False

    for frame in frames:
        frame_id = str(frame.get("frame_id", "?"))
        snapshot = frame.get("state_snapshot", {})
        if not isinstance(snapshot, dict):
            continue

        issues.extend(
            {"frame_id": frame_id, "description": description}
            for description in _negative_counterexample_issues(frame)
        )

        # A derived path-tree visual is not a replacement for the primary
        # graph, but its edges still form an executable claim that must be
        # checked against the primary edge weights and final distances.
        frame_tree_edges: set[tuple[str, str]] = set()
        for visual in _graph_visuals(frame):
            if _graph_role(visual) == "derived":
                frame_tree_edges.update(
                    _extract_tree_edges(
                        visual.get("edges", visual.get("graph_edges", []))
                    )
                )

        # A counterexample/practice graph starts a separate illustrative trace.
        # Do not compare its state against the primary execution trace; the
        # following frames may continue that illustration without repeating the
        # graph object.
        state_is_secondary = _frame_state_likely_secondary(frame)
        has_secondary = _frame_has_secondary_graph(frame)
        has_primary = _frame_has_primary_graph(frame, primary_graph_id) and not state_is_secondary
        if has_secondary and not has_primary:
            secondary_trace_active = True
            continue
        if secondary_trace_active and not has_primary:
            # A secondary example often omits the graph object in its next
            # frame.  Keep it out of the primary execution trace until a
            # primary graph is explicitly shown again.
            continue
        if has_primary:
            secondary_trace_active = False

        frame_signature = _frame_graph_signature(
            frame,
            primary_graph_id=primary_graph_id,
        )
        if frame_signature:
            if graph_signature is None:
                graph_signature = frame_signature
            elif frame_signature != graph_signature:
                issues.append({
                    "frame_id": frame_id,
                    "description": "后续帧改变了图的节点连接或边权，图结构应保持不变",
                })

        raw_dist = snapshot.get("dist", snapshot.get("distances", snapshot.get("distance")))
        current_dist: dict[str, float] | None = None
        if isinstance(raw_dist, dict):
            current_dist = {
                str(key): value
                for key, raw_value in raw_dist.items()
                if (value := _distance_value(raw_value)) is not None
            }
            if current_dist:
                final_dist = current_dist

        if current_dist is not None and previous_dist is not None:
            for vertex in set(previous_dist) & set(current_dist):
                before, after = previous_dist[vertex], current_dist[vertex]
                if math.isfinite(before) and math.isfinite(after) and after > before + 1e-9:
                    issues.append({
                        "frame_id": frame_id,
                        "description": f"dist[{vertex}] 从 {before:g} 增加到 {after:g}，最短路状态不应回退",
                    })
                if math.isfinite(before) and math.isinf(after):
                    issues.append({
                        "frame_id": frame_id,
                        "description": f"dist[{vertex}] 从有限值 {before:g} 重置为无穷大",
                    })

        raw_visited = snapshot.get("visited", snapshot.get("processed"))
        if isinstance(raw_visited, list):
            visited = {str(item) for item in raw_visited}
            if len(visited) != len(raw_visited):
                issues.append({"frame_id": frame_id, "description": "visited 包含重复顶点"})
            if vertices and not visited <= vertices:
                unknown = sorted(visited - vertices)
                issues.append({"frame_id": frame_id, "description": f"visited 包含未定义顶点: {unknown}"})
            if current_dist:
                unreachable = sorted(
                    vertex
                    for vertex in visited
                    if vertex in current_dist and math.isinf(current_dist[vertex])
                )
                if unreachable:
                    issues.append({
                        "frame_id": frame_id,
                        "description": f"visited 包含距离为无穷大的不可达顶点: {unreachable}",
                    })
            if previous_visited is not None and not previous_visited <= visited:
                issues.append({"frame_id": frame_id, "description": "visited 集合回退，移除了已处理顶点"})
            previous_visited = visited

        queue_key_present = any(key in snapshot for key in ("queue", "priority_queue", "heap", "unvisited"))
        queue_raw = next(
            (snapshot[key] for key in ("queue", "priority_queue", "heap", "unvisited") if key in snapshot),
            None,
        )
        if queue_key_present or previous_queue is not None:
            # Once a workflow starts emitting queue state, an omitted queue in
            # a later frame is treated as empty rather than as "unknown". This
            # catches a common unreachable-node bug where the queue is drained
            # without recording the final dequeue.
            queue = _queue_values(queue_raw) if queue_key_present else []
            if previous_queue and not queue and previous_visited is not None:
                current_visited = (
                    {str(item) for item in raw_visited}
                    if isinstance(raw_visited, list)
                    else previous_visited
                )
                removed = set(previous_queue) - set(current_visited)
                discardable_unreachable = bool(previous_dist) and all(
                    vertex in previous_dist and math.isinf(previous_dist[vertex])
                    for vertex in removed
                )
                if removed and not discardable_unreachable:
                    issues.append({
                        "frame_id": frame_id,
                        "description": f"队列从 {previous_queue} 变为空，但未处理顶点 {sorted(removed)}",
                    })
            if isinstance(raw_visited, list):
                overlap = sorted(set(queue) & {str(item) for item in raw_visited})
                if overlap:
                    issues.append({"frame_id": frame_id, "description": f"已处理顶点仍在队列中: {overlap}"})
            previous_queue = queue

        for key in ("shortest_path_tree", "path_tree", "predecessors", "parents", "parent"):
            if key in snapshot:
                frame_tree_edges.update(_extract_tree_edges(snapshot[key]))

        if frame_tree_edges:
            tree_edges_by_frame.setdefault(frame_id, set()).update(frame_tree_edges)

        previous_dist = current_dist or previous_dist

    if tree_edges_by_frame and final_dist and edge_map:
        for tree_frame_id, frame_tree_edges in tree_edges_by_frame.items():
            parents_by_child: dict[str, set[str]] = {}
            for parent, child in frame_tree_edges:
                parents_by_child.setdefault(child, set()).add(parent)
            for child, parents in parents_by_child.items():
                if len(parents) > 1:
                    issues.append({
                        "frame_id": tree_frame_id,
                        "description": f"最短路径树为 {child} 指定了多个前驱",
                    })

            for parent, child in frame_tree_edges:
                weights = edge_map.get((parent, child), [])
                if not weights:
                    issues.append({"frame_id": tree_frame_id, "description": f"最短路径树边 {parent}->{child} 不存在于图定义中"})
                    continue
                parent_dist = final_dist.get(parent)
                child_dist = final_dist.get(child)
                if parent_dist is None or child_dist is None or not math.isfinite(parent_dist) or not math.isfinite(child_dist):
                    continue
                if not any(math.isclose(child_dist, parent_dist + weight, rel_tol=1e-9, abs_tol=1e-9) for weight in weights):
                    issues.append({
                        "frame_id": tree_frame_id,
                        "description": f"最短路径树边 {parent}->{child} 与 dist 不一致: dist[{child}]={child_dist:g}",
                    })

    return {"checked": True, "consistent": not issues, "issues": issues}


async def validate_dsl_schema(dsl: dict[str, Any]) -> dict[str, Any]:
    """使用 Pydantic 校验 DSL 结构完整性。"""
    from schema.dsl import RenderScript

    errors: list[str] = []
    warnings: list[str] = []

    try:
        RenderScript.model_validate(dsl)
        valid = True
    except Exception as exc:  # noqa: BLE001 - validator must return structured errors
        valid = False
        errors.append(str(exc))

    # 额外检查：帧必须有 frame_id
    frames = dsl.get("frames", [])
    for i, frame in enumerate(frames):
        if not frame.get("frame_id"):
            errors.append(f"Frame at index {i} missing frame_id")
            valid = False

    # 检查：帧间 order 连续性
    if frames:
        frame_ids = [f.get("frame_id", f"unknown_{i}") for i, f in enumerate(frames)]
        if len(frame_ids) != len(set(frame_ids)):
            warnings.append("Duplicate frame_id detected")

    return {
        "valid": valid and len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


async def check_state_consistency(frames: list[dict[str, Any]]) -> dict[str, Any]:
    """检查帧间状态一致性。

    对于同一 state_snapshot 中的 key，检查帧间值的变化是否有序。
    """
    issues: list[dict[str, Any]] = []

    for i in range(len(frames) - 1):
        current = frames[i].get("state_snapshot", {})
        next_frame = frames[i + 1].get("state_snapshot", {})

        fid_current = frames[i].get("frame_id", f"f_{i}")
        fid_next = frames[i + 1].get("frame_id", f"f_{i + 1}")

        # 对于 distance_table 这类嵌套对象，检查非 ∞ 的值不应被意外重置
        for key in set(current.keys()) & set(next_frame.keys()):
            if isinstance(current[key], dict) and isinstance(next_frame[key], dict):
                for sub_key in current[key]:
                    cv = current[key].get(sub_key)
                    nv = next_frame[key].get(sub_key)
                    # 如果当前值已经是有效有限值，下一帧不应突然变回 ∞（除非显式重置）
                    if (
                        isinstance(cv, (int, float))
                        and isinstance(nv, (int, float))
                        and cv != float("inf")
                        and cv < 1_000_000
                        and (nv == float("inf") or nv > 1_000_000)
                    ):
                        issues.append({
                            "frame_pair": [fid_current, fid_next],
                            "key": f"{key}.{sub_key}",
                            "current_value": cv,
                            "next_value": nv,
                            "description": f"有效值 {cv} 在下一帧变为 {nv}，可能是状态不一致",
                        })

    return {
        "consistent": len(issues) == 0,
        "issues": issues,
    }
