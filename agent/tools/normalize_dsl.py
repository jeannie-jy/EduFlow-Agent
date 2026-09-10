"""Canonicalize model-produced RenderScript values before validation.

The Coder prompt is constrained to the RenderScript contract, but older model
responses can still contain aliases from previous DSL versions.  This module
keeps that compatibility at the boundary: it never changes the Pydantic
contract and it does not invent frame IDs or silently repair missing required
fields.  Unsupported but structurally valid visual objects degrade to cards so
model vocabulary drift cannot silently remove teaching content.
"""

from __future__ import annotations

import json
import logging
import re
from copy import deepcopy
from typing import Any

_EMPTY_QUEUE_SENTINELS = {
    "",
    "[]",
    "empty",
    "none",
    "null",
    "空",
    "空队列",
}
_QUEUE_STATE_KEYS = ("queue", "priority_queue", "heap", "unvisited")
_ALGORITHM_MARKERS = {
    "dijkstra": ("dijkstra",),
    "bellman_ford": ("bellman-ford", "bellman ford", "bellmanford"),
    "bfs": ("bfs", "广度优先"),
    "dfs": ("dfs", "深度优先"),
}


_EDGE_TEXT_RE = re.compile(
    r"(?P<source>[\w.-]+)\s*(?:→|->)\s*(?P<target>[\w.-]+)\s*"
    r"\(\s*(?P<weight>-?\d+(?:\.\d+)?)\s*\)"
)
_EDGE_OBJECT_RE = re.compile(
    r"@\{\s*from\s*=\s*(?P<source>[^;\s]+)\s*;\s*"
    r"to\s*=\s*(?P<target>[^;\s]+)\s*;\s*"
    r"weight\s*=\s*(?P<weight>-?\d+(?:\.\d+)?)\s*\}"
)


def _numeric_weight(value: Any) -> int | float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not number == number or number in {float("inf"), float("-inf")}:
        return None
    return int(number) if number.is_integer() else number


def _parse_edge_text(value: Any) -> dict[str, Any] | None:
    """Parse a declared edge string without inferring missing semantics.

    The model has historically emitted graph state as ``@{from=...}`` strings
    or as labels such as ``A→B(2)``.  These are equivalent encodings of an
    explicitly declared edge, so converting them to the canonical object form
    is a presentation/transport normalization, not a semantic repair.
    """
    if not isinstance(value, str):
        return None
    match = _EDGE_OBJECT_RE.fullmatch(value.strip()) or _EDGE_TEXT_RE.fullmatch(value.strip())
    if not match:
        return None
    weight = _numeric_weight(match.group("weight"))
    if weight is None:
        return None
    return {
        "source": match.group("source").strip(),
        "target": match.group("target").strip(),
        "weight": weight,
    }


def _parse_edge_texts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, str):
        return []
    edges: list[dict[str, Any]] = []
    for match in _EDGE_TEXT_RE.finditer(value):
        weight = _numeric_weight(match.group("weight"))
        if weight is not None:
            edges.append({
                "source": match.group("source").strip(),
                "target": match.group("target").strip(),
                "weight": weight,
            })
    return edges


def _canonical_graph_payload(graph: Any, *, label: Any = None) -> dict[str, Any] | None:
    """Return an executable graph payload when the source explicitly declares one."""
    if not isinstance(graph, dict):
        return None
    raw_nodes = graph.get("nodes") or graph.get("vertices")
    raw_edges = graph.get("edges") or graph.get("graph_edges")
    if isinstance(raw_edges, str):
        raw_edges = [raw_edges]
    edges: list[dict[str, Any]] = []
    if isinstance(raw_edges, list):
        for raw_edge in raw_edges:
            if isinstance(raw_edge, dict):
                source = raw_edge.get("source", raw_edge.get("from"))
                target = raw_edge.get("target", raw_edge.get("to"))
                weight = _numeric_weight(raw_edge.get("weight", 1))
                if source is not None and target is not None and weight is not None:
                    edges.append({"source": _text(source), "target": _text(target), "weight": weight})
            elif (edge := _parse_edge_text(raw_edge)) is not None:
                edges.append(edge)
    if not edges and isinstance(label, str):
        edges = _parse_edge_texts(label)
    if not edges:
        return None
    nodes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_node in raw_nodes if isinstance(raw_nodes, list) else []:
        node_id = raw_node.get("id", raw_node.get("label")) if isinstance(raw_node, dict) else raw_node
        if node_id is not None and _text(node_id) not in seen:
            node_id_text = _text(node_id)
            nodes.append({"id": node_id_text, "label": node_id_text})
            seen.add(node_id_text)
    for edge in edges:
        for endpoint in (edge["source"], edge["target"]):
            if endpoint not in seen:
                nodes.append({"id": endpoint, "label": endpoint})
                seen.add(endpoint)
    return {"nodes": nodes, "edges": edges, "directed": graph.get("directed", True)}


def _inject_explicit_graphs(item: dict[str, Any], *, repairs: list[str]) -> None:
    """Expose graph state in one canonical visual for renderers and graders."""
    visuals = item.get("visual_objects", [])
    if not isinstance(visuals, list):
        return
    snapshot = item.get("state_snapshot")
    state_graph = snapshot.get("graph") if isinstance(snapshot, dict) else None
    payload = _canonical_graph_payload(state_graph)
    if payload is None:
        for visual in visuals:
            if not isinstance(visual, dict) or visual.get("type") != "graph":
                continue
            identity = " ".join(_text(visual.get(key)) for key in ("id", "label", "title"))
            lowered = identity.casefold()
            if any(marker in lowered for marker in ("负环示例", "被松弛", "改为", "negative cycle example")):
                continue
            # Only explicit graph labels are parsed; prose without edge syntax
            # remains a card/graph with no executable topology.
            candidate = _canonical_graph_payload(visual, label=identity)
            if candidate is not None:
                payload = candidate
                visual.setdefault("graph_role", "primary")
                break
    if payload is None:
        return

    primary = next(
        (
            visual for visual in visuals
            if isinstance(visual, dict)
            and visual.get("type") == "graph"
            and visual.get("graph_role", visual.get("role", "primary")) == "primary"
        ),
        None,
    )
    if primary is None:
        primary = {"id": "primary_graph", "type": "graph", "graph_role": "primary"}
        visuals.insert(0, primary)
        repairs.append("explicit_graph_state_to_visual")
    before = (primary.get("nodes"), primary.get("edges"), primary.get("directed"))
    primary["nodes"] = deepcopy(payload["nodes"])
    primary["edges"] = deepcopy(payload["edges"])
    primary["directed"] = payload.get("directed", True)
    primary["graph_role"] = "primary"
    after = (primary.get("nodes"), primary.get("edges"), primary.get("directed"))
    if before != after:
        repairs.append("graph_edges_to_canonical_objects")


def _normalise_queue_sentinels(snapshot: Any) -> Any:
    """Canonicalize scalar empty-queue markers while preserving real node lists."""
    if not isinstance(snapshot, dict):
        return snapshot
    result = deepcopy(snapshot)
    for key in _QUEUE_STATE_KEYS:
        value = result.get(key)
        if isinstance(value, str) and value.strip().casefold() in _EMPTY_QUEUE_SENTINELS:
            result[key] = []
    return result


def _infer_algorithm(topic: Any) -> str | None:
    text = _text(topic).casefold()
    for algorithm, markers in _ALGORITHM_MARKERS.items():
        if any(marker in text for marker in markers):
            return algorithm
    return None


def _queue_entry(value: Any) -> dict[str, Any] | None:
    """Convert supported legacy queue encodings to one canonical object."""
    if isinstance(value, dict):
        vertex = value.get("vertex", value.get("node", value.get("id")))
        priority = value.get("priority", value.get("distance", value.get("key")))
    elif isinstance(value, (list, tuple)):
        vertex = value[0] if value else None
        priority = value[1] if len(value) > 1 else None
    elif isinstance(value, str):
        text = value.strip()
        match = re.fullmatch(r"(.+?)\s*\(([^()]*)\)", text)
        if match:
            vertex, priority = match.group(1).strip(), match.group(2).strip()
        else:
            vertex, priority = text, None
    else:
        vertex, priority = value, None
    if vertex is None or not str(vertex).strip():
        return None
    return {"vertex": str(vertex).strip(), "priority": priority}


def _edge_scan_entry(value: Any) -> dict[str, Any] | None:
    """Convert a Bellman-Ford edge token into the non-priority scan form."""
    if isinstance(value, dict):
        source = value.get("source", value.get("from"))
        target = value.get("target", value.get("to"))
        weight = value.get("weight", value.get("priority"))
        if source is not None and target is not None:
            parsed_weight = _numeric_weight(weight)
            return {"source": _text(source), "target": _text(target), "weight": parsed_weight}
        value = value.get("vertex", value.get("id"))
    if isinstance(value, str):
        edge = _parse_edge_text(value)
        if edge is not None:
            return edge
        match = re.fullmatch(r"(.+?)\s*(?:→|->)\s*(.+)", value.strip())
        if match:
            return {"source": match.group(1).strip(), "target": match.group(2).strip(), "weight": None}
    return None


def _normalise_algorithm_snapshot(
    snapshot: Any,
    *,
    algorithm: str | None,
    repairs: list[str],
) -> Any:
    """Canonicalize algorithm state aliases without changing semantic values."""
    if not isinstance(snapshot, dict):
        return snapshot
    result = _normalise_queue_sentinels(snapshot)
    inferred = result.get("algorithm") or algorithm
    # Topic inference alone is not enough to opt every explanatory/comparison
    # frame into the executable protocol.  Only frames that actually carry
    # algorithm state (or explicitly declare ``algorithm``) receive the
    # versioned schema; otherwise concept-only frames would fail because they
    # have no queue/dist fields to validate.
    has_algorithm_state = bool(result.get("algorithm")) or any(
        key in result
        for key in ("dist", "distances", "visited", "processed", *_QUEUE_STATE_KEYS)
    )
    if not has_algorithm_state:
        return result
    if inferred:
        if result.get("algorithm") != inferred:
            result["algorithm"] = inferred
            repairs.append("algorithm_alias")
        if result.get("schema_version") != "algorithm-trace-v1":
            result["schema_version"] = "algorithm-trace-v1"
            repairs.append("algorithm_schema_version")
    canonical_algorithm = str(inferred) if inferred else None

    if "dist" not in result:
        for alias in ("distances", "distance"):
            if isinstance(result.get(alias), dict):
                result["dist"] = deepcopy(result[alias])
                repairs.append(f"{alias}_to_dist")
                break
    if canonical_algorithm:
        for alias in ("distances", "distance"):
            if alias in result:
                result.pop(alias, None)
    if "visited" not in result and isinstance(result.get("processed"), list):
        result["visited"] = list(result["processed"])
        repairs.append("processed_to_visited")
    if canonical_algorithm:
        result.pop("processed", None)

    if "predecessor" not in result:
        for alias in ("prev", "predecessors", "parents", "parent"):
            if isinstance(result.get(alias), dict):
                result["predecessor"] = deepcopy(result[alias])
                repairs.append(f"{alias}_to_predecessor")
                break
    if canonical_algorithm:
        for alias in ("prev", "predecessors", "parents", "parent"):
            result.pop(alias, None)

    queue_key = next((key for key in _QUEUE_STATE_KEYS if key in result), None)
    if queue_key is not None and canonical_algorithm:
        raw_queue = result.get(queue_key)
        if isinstance(raw_queue, str) and raw_queue.strip().casefold() in _EMPTY_QUEUE_SENTINELS:
            result["queue"] = []
        elif isinstance(raw_queue, list):
            result["queue"] = [
                entry
                for item in raw_queue
                if (entry := _queue_entry(item)) is not None
            ]
        else:
            result["queue"] = []
        if canonical_algorithm == "bellman_ford":
            raw_items = raw_queue if isinstance(raw_queue, list) else []
            scan = [entry for item in raw_items if (entry := _edge_scan_entry(item)) is not None]
            # Bellman-Ford scans a declared edge list; it does not maintain a
            # Dijkstra-style priority queue.  Preserve the edge sequence under
            # edge_scan and keep the canonical queue empty.
            if scan and all("source" in entry and "target" in entry for entry in scan):
                result["edge_scan"] = scan
                result["queue"] = []
                repairs.append("bellman_queue_to_edge_scan")
            if queue_key != "queue":
                repairs.append(f"{queue_key}_to_queue")
        elif queue_key != "queue":
            repairs.append(f"{queue_key}_to_queue")
        if any(isinstance(item, (list, tuple, str)) for item in (raw_queue or []) if isinstance(raw_queue, list)):
            repairs.append("queue_entries_to_objects")
        for alias in _QUEUE_STATE_KEYS:
            if alias != "queue":
                result.pop(alias, None)
    elif canonical_algorithm:
        # Explanatory/summary frames may omit queue, but the versioned
        # protocol carries an explicit empty value after normalization.
        result["queue"] = []
        repairs.append("bellman_queue_default" if canonical_algorithm == "bellman_ford" else "algorithm_queue_default")
    elif queue_key is not None:
        # Generic lessons may still use legacy queue fields. Preserve those
        # keys for backwards-compatible rendering; algorithm lessons opt into
        # the single canonical queue field above.
        for alias in _QUEUE_STATE_KEYS:
            if alias in result:
                result[alias] = _normalise_queue_sentinels({alias: result[alias]})[alias]
    return result


logger = logging.getLogger(__name__)

_AUDIENCES = {"undergraduate_cs", "graduate_cs", "high_school", "self_learner"}
_DIFFICULTIES = {"beginner", "intermediate", "advanced"}
_OBJECT_TYPES = {
    "node", "edge", "array", "linked_list", "tree", "graph", "table",
    "code_block", "memory_block", "process", "timeline", "formula", "card",
    "mindmap",
}
_ANIMATION_TYPES = {
    "appear", "disappear", "highlight", "transform", "move", "update_value",
    "compare", "swap", "relax_edge", "enqueue", "dequeue", "split", "merge",
    "schedule", "lock", "unlock",
}
_CHECK_TYPES = {"distance_consistency", "state_consistency", "invariant", "boundary"}
_PARAM_TYPES = {"number", "string", "boolean", "enum", "graph", "array", "code"}


def _text(value: Any, default: str = "") -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return default
    return str(value)


def _json_text(value: Any, default: str = "") -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return default
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        return str(value)


def _canonical_audience(value: Any) -> str:
    raw = _text(value, "undergraduate_cs").strip().casefold()
    if raw in _AUDIENCES:
        return raw
    # Older planner prompts encoded difficulty in the audience value.
    for suffix in ("_beginner", "_intermediate", "_advanced"):
        if raw.endswith(suffix) and raw[: -len(suffix)] in _AUDIENCES:
            return raw[: -len(suffix)]
    aliases = {
        "undergraduate": "undergraduate_cs",
        "college": "undergraduate_cs",
        "本科生": "undergraduate_cs",
        "本科": "undergraduate_cs",
        "研究生": "graduate_cs",
        "高中生": "high_school",
        "自学": "self_learner",
        "self-learning": "self_learner",
    }
    return aliases.get(raw, "undergraduate_cs")


def _canonical_param_type(value: Any) -> str:
    raw = _text(value, "string").strip().casefold()
    aliases = {
        "integer": "number",
        "float": "number",
        "select": "enum",
        "choice": "enum",
        "list": "array",
        "sequence": "array",
        "code_snippet": "code",
    }
    return aliases.get(raw, raw if raw in _PARAM_TYPES else "string")


def _canonical_visibility(value: Any) -> str:
    raw = _text(value, "student").strip().casefold()
    aliases = {
        "visible": "student",
        "student_visible": "student",
        "public": "student",
        "hidden": "teacher",
        "teacher_only": "teacher",
        "private": "teacher",
    }
    return aliases.get(raw, raw if raw in {"student", "teacher"} else "student")


def _canonical_scope(value: Any) -> str:
    raw = _text(value, "all_frames").strip().casefold()
    aliases = {
        "all": "all_frames",
        "global": "all_frames",
        "all_frame": "all_frames",
        "none": "local",
        "frame": "local",
        "current": "local",
        "graph": "local",
        "table": "local",
        "animation": "local",
        "visual": "local",
    }
    if raw in {"local", "all_frames"}:
        return raw
    return aliases.get(raw, "all_frames")


def _normalise_parameter(parameter: Any) -> dict[str, Any] | None:
    if not isinstance(parameter, dict):
        return None
    item = deepcopy(parameter)
    if "param_type" not in item and "type" in item:
        item["param_type"] = item.get("type")
    if "default_value" not in item and "default" in item:
        item["default_value"] = item.get("default")
    if "current_value" not in item and "value" in item:
        item["current_value"] = item.get("value")
    item["key"] = _text(item.get("key"), "parameter")
    item["label"] = _text(item.get("label"), item["key"])
    item["param_type"] = _canonical_param_type(item.get("param_type"))
    item["visibility"] = _canonical_visibility(item.get("visibility"))
    item["recompute_scope"] = _canonical_scope(item.get("recompute_scope"))
    frame_ids = item.get("affects_frame_ids", [])
    item["affects_frame_ids"] = (
        [_text(value) for value in frame_ids if value is not None]
        if isinstance(frame_ids, list)
        else []
    )
    return item


def _normalise_visual_object(value: Any, index: int) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    item = deepcopy(value)
    raw_type = _text(item.get("type"), "card").strip().casefold()
    aliases = {
        "mind_map": "mindmap",
        "mind-map": "mindmap",
        "text": "card",
        "text_block": "card",
        "label": "card",
        "annotation": "card",
        "diagram": "graph" if item.get("nodes") or item.get("edges") else "card",
        "button": "card",
        "flowchart": "graph",
        "quiz": "card",
        "question": "card",
        "multiple_choice": "card",
        "choice": "card",
    }
    object_type = aliases.get(raw_type, raw_type)
    if raw_type == "chart":
        data = item.get("data")
        rows = [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []
        if rows:
            headers = list(rows[0])
            item["headers"] = headers
            item["rows"] = [[row.get(header, "") for header in headers] for row in rows]
            object_type = "table"
        elif isinstance(data, list):
            # Preserve primitive chart samples as a renderable one-column table
            # instead of silently dropping the model's visual object.
            item["headers"] = ["value"]
            item["rows"] = [[value] for value in data]
            object_type = "table"
        else:
            # A chart without tabular data cannot be rendered as a chart in the
            # current DSL. Keep its explanation as a card so the frame remains
            # visible and the unsupported type is not silently discarded.
            object_type = "card"
    if object_type not in _OBJECT_TYPES:
        logger.warning(
            "Converting unsupported visual object type=%s to card", raw_type
        )
        object_type = "card"
    item["type"] = object_type
    item["id"] = _text(item.get("id"), f"visual_{index + 1}")

    if object_type == "card":
        item["title"] = _text(item.get("title"), _text(item.get("label"), "说明"))
        fallback_content = {
            key: child
            for key, child in item.items()
            if key not in {"id", "type", "title", "label", "position", "style"}
        }
        item["content"] = _json_text(
            item.get(
                "content",
                item.get(
                    "text",
                    item.get("data", item.get("label", fallback_content)),
                ),
            )
        )
    elif object_type == "array":
        cells = item.get("cells", item.get("values", []))
        if isinstance(cells, dict):
            cells = [cells]
        if not isinstance(cells, list):
            cells = []
        item["cells"] = [
            cell if isinstance(cell, dict) else {"index": position, "value": cell}
            for position, cell in enumerate(cells)
        ]
    elif object_type == "graph":
        # Older generators wrapped graph payloads under ``data`` and used
        # ``vertices``/``from``/``to`` aliases.  Expose the same payload on
        # the canonical graph fields so renderers and reference checks inspect
        # the actual topology instead of an empty shell.
        data = item.get("data") if isinstance(item.get("data"), dict) else {}
        raw_nodes = item.get("nodes") or item.get("vertices") or data.get("nodes") or data.get("vertices")
        raw_edges = item.get("edges") or item.get("graph_edges") or data.get("edges") or data.get("graph_edges")
        if isinstance(raw_nodes, list):
            nodes = []
            seen_nodes: set[str] = set()
            for node in raw_nodes:
                if isinstance(node, dict):
                    node_id = node.get("id", node.get("label"))
                    normalised_node = dict(node)
                    if node_id is not None:
                        normalised_node["id"] = _text(node_id)
                else:
                    node_id = node
                    normalised_node = {"id": _text(node_id), "label": _text(node_id)}
                if node_id is not None and _text(node_id) not in seen_nodes:
                    nodes.append(normalised_node)
                    seen_nodes.add(_text(node_id))
            item["nodes"] = nodes
        if isinstance(raw_edges, list):
            edges = []
            for edge in raw_edges:
                if not isinstance(edge, dict):
                    parsed = _parse_edge_text(edge)
                    if parsed is not None:
                        edges.append(parsed)
                    continue
                source = edge.get("source", edge.get("from"))
                target = edge.get("target", edge.get("to"))
                if source is None or target is None:
                    continue
                canonical_edge = dict(edge)
                canonical_edge["source"] = _text(source)
                canonical_edge["target"] = _text(target)
                canonical_edge.pop("from", None)
                canonical_edge.pop("to", None)
                edges.append(canonical_edge)
            item["edges"] = edges
    elif object_type == "mindmap" and not isinstance(item.get("root"), dict):
        item["root"] = {"label": _text(item.get("root"), item.get("label", ""))}
    elif object_type == "code_block":
        if _text(item.get("language"), "text").casefold() in {"pseudocode", "pseudo"}:
            item["language"] = "text"
    elif object_type == "edge":
        item["source"] = _text(item.get("source"))
        item["target"] = _text(item.get("target"))
    elif object_type == "node":
        if item.get("node_type") not in {"circle", "square", "diamond"}:
            item["node_type"] = "circle"
    return item


def _normalise_animation(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    item = deepcopy(value)
    raw_type = _text(item.get("type"), "highlight").strip().casefold()
    aliases = {
        "show": "appear",
        "enter": "appear",
        "hide": "disappear",
        "exit": "disappear",
        "pulse": "highlight",
        "change": "update_value",
        "update": "update_value",
        "rotate": "transform",
    }
    animation_type = aliases.get(raw_type, raw_type)
    if animation_type not in _ANIMATION_TYPES:
        return None
    item["type"] = animation_type
    item["target"] = _text(item.get("target"), "")
    return item


def _normalise_hook(value: Any, index: int) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    item = deepcopy(value)
    raw_type = _text(item.get("type"), "button").strip().casefold()
    aliases = {"choice": "select", "range": "slider", "toggle": "switch"}
    hook_type = aliases.get(raw_type, raw_type)
    if hook_type not in {"slider", "select", "switch", "button"}:
        return None
    item["type"] = hook_type
    param = item.get("param", item.get("parameter", item.get("key", item.get("name"))))
    if isinstance(param, dict):
        param = param.get("key", param.get("parameter", param.get("name")))
    item["param"] = _text(param, f"interaction_{index + 1}")
    if isinstance(item.get("range"), dict):
        limits = item["range"]
        item["range"] = [limits.get("min", 0), limits.get("max", 1)]
    if isinstance(item.get("options"), list):
        options = []
        for option in item["options"]:
            if isinstance(option, dict):
                options.append(_text(option.get("value"), _text(option.get("label"))))
            else:
                options.append(_text(option))
        item["options"] = options
    return item


def _normalise_check(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    item = deepcopy(value)
    raw_type = _text(item.get("type"), "invariant").strip().casefold()
    aliases = {
        "sort_check": "invariant",
        "range_check": "boundary",
        "distance_check": "distance_consistency",
        "state_check": "state_consistency",
    }
    item["type"] = aliases.get(raw_type, raw_type if raw_type in _CHECK_TYPES else "invariant")
    rule = item.get("rule", item.get("description", item.get("message")))
    if rule is None:
        rule = {key: item[key] for key in ("target", "expected", "actual") if key in item}
    item["rule"] = _json_text(rule, "deterministic check")
    return item


def _normalise_frame(
    frame: Any,
    *,
    algorithm: str | None = None,
    repairs: list[str] | None = None,
) -> dict[str, Any] | None:
    if not isinstance(frame, dict):
        return None
    item = deepcopy(frame)
    if "state_snapshot" in item:
        item["state_snapshot"] = _normalise_algorithm_snapshot(
            item["state_snapshot"],
            algorithm=algorithm,
            repairs=repairs if repairs is not None else [],
        )
    visual_objects = item.get("visual_objects", [])
    item["visual_objects"] = [
        normalised
        for index, value in enumerate(visual_objects if isinstance(visual_objects, list) else [])
        if (normalised := _normalise_visual_object(value, index)) is not None
    ]
    _inject_explicit_graphs(item, repairs=repairs if repairs is not None else [])
    for field, normaliser in (
        ("animations", _normalise_animation),
        ("interaction_hooks", _normalise_hook),
        ("checks", _normalise_check),
    ):
        if field not in item:
            continue
        values = item.get(field, [])
        output = []
        if isinstance(values, list):
            for index, value in enumerate(values):
                normalised = normaliser(value, index) if field == "interaction_hooks" else normaliser(value)
                if normalised is not None:
                    output.append(normalised)
        item[field] = output
    if "depends_on_parameters" in item and not isinstance(item.get("depends_on_parameters"), list):
        item["depends_on_parameters"] = []
    return item


def normalize_dsl(dsl: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``dsl`` with known legacy aliases canonicalized."""
    if not isinstance(dsl, dict):
        return {}
    result = deepcopy(dsl)
    repairs: list[str] = []
    result["audience"] = _canonical_audience(result.get("audience"))
    difficulty = _text(result.get("difficulty"), "intermediate").casefold()
    result["difficulty"] = difficulty if difficulty in _DIFFICULTIES else "intermediate"
    parameters = result.get("parameters", [])
    result["parameters"] = [
        normalised
        for value in (parameters if isinstance(parameters, list) else [])
        if (normalised := _normalise_parameter(value)) is not None
    ]
    frames = result.get("frames", [])
    algorithm = _infer_algorithm(result.get("topic"))
    result["frames"] = [
        normalised
        for value in (frames if isinstance(frames, list) else [])
        if (normalised := _normalise_frame(value, algorithm=algorithm, repairs=repairs)) is not None
    ]
    if repairs:
        result["normalization_report"] = {
            "applied": True,
            "schema_version": "algorithm-trace-v1" if algorithm else None,
            "repair_types": sorted(set(repairs)),
            "repair_count": len(repairs),
        }
    return result


__all__ = ["normalize_dsl"]
