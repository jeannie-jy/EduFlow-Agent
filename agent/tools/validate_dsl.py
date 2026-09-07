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
_SECONDARY_GRAPH_MARKERS = (
    "negative",
    "counterexample",
    "practice",
    "exercise",
    "反例",
    "练习",
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
    if any(_graph_role(graph) == "primary" for graph in _graph_visuals(frame)) and not explicitly_wrong_trace:
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
    if not any(marker in topic_text for marker in _SHORTEST_PATH_MARKERS):
        return result

    frames = result.get("frames", [])
    if not isinstance(frames, list):
        return result
    primary_graph_id = _primary_graph_id(frames)
    previous_visited: list[Any] = []
    secondary_trace_active = False
    repairs = 0

    for frame in frames:
        if not isinstance(frame, dict):
            continue
        has_secondary = _frame_has_secondary_graph(frame)
        has_primary = _frame_has_primary_graph(frame, primary_graph_id)
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
        visited_key = (
            "visited"
            if isinstance(snapshot.get("visited"), list)
            else "processed"
            if isinstance(snapshot.get("processed"), list)
            else None
        )
        if visited_key is None:
            continue

        raw_dist = snapshot.get(
            "dist", snapshot.get("distances", snapshot.get("distance"))
        )
        distances = {
            str(vertex): distance
            for vertex, value in raw_dist.items()
            if (distance := _distance_value(value)) is not None
        } if isinstance(raw_dist, dict) else {}

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
    if not any(marker in topic_text for marker in _SHORTEST_PATH_MARKERS):
        return {"checked": False, "consistent": True, "issues": []}

    issues: list[dict[str, Any]] = []
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
        has_secondary = _frame_has_secondary_graph(frame)
        has_primary = _frame_has_primary_graph(frame, primary_graph_id)
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
