"""Compile interactive teaching frames into a video-oriented storyboard.

The interactive renderer benefits from controls, checks and source code.  A
teaching video has a different job: keep the main data structure stable and
make the state transition legible.  This compiler is deliberately
deterministic so exporting an already-reviewed trace never changes its
algorithmic claims.
"""

from __future__ import annotations

import json
import math
from copy import deepcopy
from typing import Any

_CODE_INTENT_MARKERS = (
    "代码",
    "伪代码",
    "实现",
    "编程",
    "源码",
    "code",
    "implementation",
    "pseudocode",
    "python",
    "java",
    "c++",
    "javascript",
)


def _text(frame: dict[str, Any]) -> str:
    return f"{frame.get('title', '')} {frame.get('learning_goal', '')} {frame.get('narration', '')}".casefold()


def _contains_code_intent(text: str) -> bool:
    text = text.casefold()
    return any(marker in text for marker in _CODE_INTENT_MARKERS)


def _json_signature(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _changed_state_keys(previous: dict[str, Any], current: dict[str, Any]) -> list[str]:
    return sorted(
        key
        for key in set(previous) | set(current)
        if _json_signature(previous.get(key)) != _json_signature(current.get(key))
    )


def _display_value(value: Any) -> str:
    if value is None:
        return "∞"
    if isinstance(value, float) and math.isinf(value):
        return "∞"
    text = str(value)
    return "∞" if text.casefold() in {"inf", "infinity", "null", "none"} else text


def _display_predecessor(value: Any) -> str:
    return "—" if value is None or str(value).casefold() in {"null", "none", ""} else str(value)


def _graph_node_order(graph: dict[str, Any], distances: dict[str, Any]) -> list[str]:
    ordered = [
        str(node.get("id", node.get("label")))
        for node in graph.get("nodes", [])
        if isinstance(node, dict) and node.get("id", node.get("label")) is not None
    ]
    ordered.extend(str(node_id) for node_id in distances if str(node_id) not in ordered)
    return ordered


def _state_panel(frame: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any] | None:
    snapshot = frame.get("state_snapshot")
    if not isinstance(snapshot, dict):
        return None
    distances = snapshot.get("dist", snapshot.get("distances", snapshot.get("distance")))
    if not isinstance(distances, dict) or not distances:
        return None
    predecessors = snapshot.get(
        "predecessor",
        snapshot.get("predecessors", snapshot.get("parent", snapshot.get("parents", {}))),
    )
    if not isinstance(predecessors, dict):
        predecessors = {}
    rows = [
        [
            node_id,
            _display_value(distances.get(node_id)),
            _display_predecessor(predecessors.get(node_id)),
        ]
        for node_id in _graph_node_order(graph, distances)
    ]
    return {
        "id": "video_state_panel",
        "type": "table",
        "label": "距离与前驱",
        "headers": ["节点", "距离", "前驱"],
        "rows": rows,
    }


def compile_video_storyboard(dsl: dict[str, Any]) -> dict[str, Any]:
    """Return a video-specific copy of a canonical RenderScript artifact.

    Rules intentionally stay small and auditable:

    * code is shown only when the lesson explicitly teaches implementation;
    * graph traces receive a stable distance/predecessor dashboard;
    * each scene records its semantic delta and persistent object identities.
    """
    result = deepcopy(dsl)
    raw_frames = result.get("frames")
    frames = [frame for frame in raw_frames if isinstance(frame, dict)] if isinstance(raw_frames, list) else []
    topic = str(result.get("topic") or "")
    code_budget = max(1, math.ceil(len(frames) * 0.2)) if frames else 0
    code_frames = [
        index
        for index, frame in enumerate(frames)
        if any(
            isinstance(obj, dict) and obj.get("type") == "code_block"
            for obj in frame.get("visual_objects", [])
        )
    ]
    explicit_code_frames = [index for index in code_frames if _contains_code_intent(_text(frames[index]))]
    if not explicit_code_frames and _contains_code_intent(topic):
        explicit_code_frames = code_frames
    kept_code_frames = set(explicit_code_frames[:code_budget])

    removed_code_blocks = 0
    panels_added = 0
    changed_scenes = 0
    previous_snapshot: dict[str, Any] = {}
    previous_ids: set[str] = set()

    for index, frame in enumerate(frames):
        visuals = [obj for obj in frame.get("visual_objects", []) if isinstance(obj, dict)]
        original_count = len(visuals)
        if index not in kept_code_frames:
            without_code = [obj for obj in visuals if obj.get("type") != "code_block"]
            # Never turn a frame into an empty screen.  A lone code object is
            # retained until the upstream storyboard can be regenerated.
            if without_code:
                removed_code_blocks += original_count - len(without_code)
                visuals = without_code

        graph = next((obj for obj in visuals if obj.get("type") == "graph"), None)
        has_table = any(obj.get("type") == "table" for obj in visuals)
        if graph is not None and not has_table:
            panel = _state_panel(frame, graph)
            if panel is not None:
                visuals.append(panel)
                panels_added += 1

        frame["visual_objects"] = visuals
        snapshot = frame.get("state_snapshot") if isinstance(frame.get("state_snapshot"), dict) else {}
        current_ids = {str(obj.get("id")) for obj in visuals if obj.get("id") is not None}
        changed_keys = _changed_state_keys(previous_snapshot, snapshot)
        if changed_keys:
            changed_scenes += 1
        frame["video_transition"] = {
            "persistent_object_ids": sorted(previous_ids & current_ids),
            "added_object_ids": sorted(current_ids - previous_ids),
            "removed_object_ids": sorted(previous_ids - current_ids),
            "changed_state_keys": changed_keys,
        }
        previous_snapshot = snapshot
        previous_ids = current_ids

    result["frames"] = frames
    result["video_storyboard_report"] = {
        "compiled": True,
        "scene_count": len(frames),
        "changed_scene_count": changed_scenes,
        "code_scene_count": len(kept_code_frames),
        "removed_code_blocks": removed_code_blocks,
        "state_panels_added": panels_added,
    }
    return result


__all__ = ["compile_video_storyboard"]
