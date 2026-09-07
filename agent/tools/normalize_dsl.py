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
from copy import deepcopy
from typing import Any

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


def _normalise_frame(frame: Any) -> dict[str, Any] | None:
    if not isinstance(frame, dict):
        return None
    item = deepcopy(frame)
    visual_objects = item.get("visual_objects", [])
    item["visual_objects"] = [
        normalised
        for index, value in enumerate(visual_objects if isinstance(visual_objects, list) else [])
        if (normalised := _normalise_visual_object(value, index)) is not None
    ]
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
    result["frames"] = [
        normalised
        for value in (frames if isinstance(frames, list) else [])
        if (normalised := _normalise_frame(value)) is not None
    ]
    return result


__all__ = ["normalize_dsl"]
