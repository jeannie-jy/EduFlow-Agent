"""Bounded, deterministic summaries for RenderScript version review."""

from __future__ import annotations

from typing import Any

_FRAME_FIELDS = (
    "title",
    "learning_goal",
    "narration",
    "visual_objects",
    "state_snapshot",
    "animations",
    "interaction_hooks",
    "checks",
    "depends_on_parameters",
)


def _indexed(items: Any, key: str) -> tuple[list[str], dict[str, dict[str, Any]]]:
    if not isinstance(items, list):
        return [], {}
    ordered: list[str] = []
    indexed: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict) or not item.get(key):
            continue
        identifier = str(item[key])
        if identifier in indexed:
            continue
        ordered.append(identifier)
        indexed[identifier] = item
    return ordered, indexed


def diff_dsl_versions(
    before: dict[str, Any] | None, after: dict[str, Any] | None
) -> dict[str, Any]:
    """Describe semantic DSL changes without returning an unbounded JSON patch."""
    old = before or {}
    new = after or {}
    old_order, old_frames = _indexed(old.get("frames"), "frame_id")
    new_order, new_frames = _indexed(new.get("frames"), "frame_id")

    added_ids = [frame_id for frame_id in new_order if frame_id not in old_frames]
    removed_ids = [frame_id for frame_id in old_order if frame_id not in new_frames]
    modified_frames = []
    for frame_id in old_order:
        if frame_id not in new_frames:
            continue
        changed_fields = [
            field
            for field in _FRAME_FIELDS
            if old_frames[frame_id].get(field) != new_frames[frame_id].get(field)
        ]
        if changed_fields:
            modified_frames.append(
                {"frame_id": frame_id, "changed_fields": changed_fields}
            )

    _, old_params = _indexed(old.get("parameters"), "key")
    _, new_params = _indexed(new.get("parameters"), "key")
    parameter_changes = []
    for key in sorted(set(old_params) | set(new_params)):
        if key not in old_params:
            change = "added"
        elif key not in new_params:
            change = "removed"
        elif old_params[key] != new_params[key]:
            change = "modified"
        else:
            continue
        parameter_changes.append({"key": key, "change": change})

    metadata_fields = (
        "topic",
        "audience",
        "difficulty",
        "teaching_strategy",
        "knowledge_graph",
        "assets",
        "export_targets",
    )
    metadata_changed = [
        field for field in metadata_fields if old.get(field) != new.get(field)
    ]
    common_old_order = [frame_id for frame_id in old_order if frame_id in new_frames]
    common_new_order = [frame_id for frame_id in new_order if frame_id in old_frames]
    reordered = common_old_order != common_new_order

    return {
        "summary": {
            "frames_added": len(added_ids),
            "frames_removed": len(removed_ids),
            "frames_modified": len(modified_frames),
            "parameters_changed": len(parameter_changes),
            "metadata_fields_changed": len(metadata_changed),
            "frame_order_changed": reordered,
        },
        "frames": {
            "added": added_ids,
            "removed": removed_ids,
            "modified": modified_frames,
            "order_changed": reordered,
        },
        "parameters": parameter_changes,
        "metadata_changed": metadata_changed,
    }
