"""Deterministic scope resolution and merge rules for partial regeneration."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

_SCOPE_TYPES = {"single_frame", "frame_range", "from_frame", "all_frames"}


def normalize_regeneration_scope(scope: dict[str, Any] | None) -> dict[str, Any]:
    value = dict(scope or {"type": "all_frames"})
    scope_type = value.get("type")
    if scope_type not in _SCOPE_TYPES:
        raise ValueError("Unsupported regeneration scope")
    raw_ids = value.get("frame_ids", [])
    if raw_ids is None:
        raw_ids = []
    if not isinstance(raw_ids, list) or len(raw_ids) > 100:
        raise ValueError("frame_ids must be a bounded list")
    frame_ids = []
    for frame_id in raw_ids:
        if not isinstance(frame_id, str) or not frame_id or len(frame_id) > 100:
            raise ValueError("Invalid frame_id")
        if frame_id not in frame_ids:
            frame_ids.append(frame_id)
    required_counts = {
        "single_frame": 1,
        "from_frame": 1,
        "frame_range": 2,
    }
    required_count = required_counts.get(scope_type)
    if required_count is not None and len(frame_ids) != required_count:
        raise ValueError(f"{scope_type} requires {required_count} frame id(s)")
    if scope_type == "all_frames":
        frame_ids = []
    return {"type": scope_type, "frame_ids": frame_ids}


def resolve_target_frame_ids(
    frames: list[dict[str, Any]], scope: dict[str, Any] | None
) -> set[str]:
    normalized = normalize_regeneration_scope(scope)
    ordered_ids = [str(frame.get("frame_id", "")) for frame in frames]
    ordered_ids = [frame_id for frame_id in ordered_ids if frame_id]
    requested = normalized["frame_ids"]
    scope_type = normalized["type"]
    if scope_type == "all_frames":
        return set(ordered_ids)
    if scope_type == "single_frame":
        return {requested[0]} & set(ordered_ids)
    indexes = [ordered_ids.index(frame_id) for frame_id in requested if frame_id in ordered_ids]
    if not indexes:
        return set()
    if scope_type == "from_frame":
        return set(ordered_ids[min(indexes):])
    return set(ordered_ids[min(indexes): max(indexes) + 1])


def merge_scoped_dsl(
    existing: dict[str, Any],
    generated: dict[str, Any],
    scope: dict[str, Any] | None,
    locked_frame_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Merge only target frames, preserving stable IDs and all protected frames."""
    old_frames = [frame for frame in existing.get("frames", []) if isinstance(frame, dict)]
    targets = resolve_target_frame_ids(old_frames, scope)
    locked = set(locked_frame_ids or [])
    replaceable = targets - locked
    generated_frames = [
        frame for frame in generated.get("frames", []) if isinstance(frame, dict)
    ]
    by_id = {
        str(frame.get("frame_id")): frame
        for frame in generated_frames
        if frame.get("frame_id")
    }
    # Do not consume a frame that is an exact-ID replacement for a later target
    # as a positional fallback for an earlier target.
    positional = iter(
        frame
        for frame in generated_frames
        if str(frame.get("frame_id", "")) not in replaceable
    )
    merged_frames: list[dict[str, Any]] = []
    for old in old_frames:
        frame_id = str(old.get("frame_id", ""))
        if frame_id not in replaceable:
            merged_frames.append(deepcopy(old))
            continue
        replacement = by_id.get(frame_id)
        if replacement is None:
            replacement = next(positional, None)
        if replacement is None:
            merged_frames.append(deepcopy(old))
            continue
        updated = deepcopy(replacement)
        updated["frame_id"] = frame_id
        merged_frames.append(updated)

    # A frame-scoped operation must not silently mutate parameters, assets, or
    # project metadata. Those have separate update/recompute lifecycles.
    merged = deepcopy(existing)
    merged["frames"] = merged_frames
    return merged
