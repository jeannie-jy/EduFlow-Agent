"""Consistency checks for immutable versions and the editable Frames projection."""

from __future__ import annotations

import uuid
from copy import deepcopy
from typing import Any

from services.project_persistence import compact_frames_artifact_reference


def normalize_frame(frame: dict[str, Any]) -> dict[str, Any]:
    """Normalize generated and row-serialized frames to the same comparison shape."""
    return {
        "frame_id": frame.get("frame_id"),
        "title": frame.get("title") or "",
        "learning_goal": frame.get("learning_goal") or "",
        "narration": frame.get("narration") or "",
        "visual_objects": deepcopy(frame.get("visual_objects") or []),
        "state_snapshot": deepcopy(frame.get("state_snapshot") or {}),
        "animations": deepcopy(frame.get("animations") or []),
        "interaction_hooks": deepcopy(frame.get("interaction_hooks") or []),
        "checks": deepcopy(frame.get("checks") or []),
        "quality_status": frame.get("quality_status") or "pending",
        "is_locked": bool(frame.get("is_locked", False)),
    }


def snapshot_reference_version(snapshot: dict[str, Any] | None) -> str | None:
    module_outputs = (snapshot or {}).get("module_outputs")
    if not isinstance(module_outputs, dict):
        return None
    frames_output = module_outputs.get("frames")
    if not isinstance(frames_output, dict):
        return None
    reference = frames_output.get("artifact_ref")
    if not isinstance(reference, dict):
        return None
    if reference.get("type") != "project_version_frames":
        return None
    version_id = reference.get("version_id")
    return version_id if isinstance(version_id, str) else None


def has_frames_module(snapshot: dict[str, Any] | None) -> bool:
    module_outputs = (snapshot or {}).get("module_outputs")
    return isinstance(module_outputs, dict) and isinstance(
        module_outputs.get("frames"), dict
    )


def inspect_project_artifacts(
    *,
    project_snapshot: dict[str, Any] | None,
    current_version_id: uuid.UUID | None,
    current_version_snapshot: dict[str, Any] | None,
    frame_projection: list[dict[str, Any]],
) -> list[str]:
    """Return stable issue codes without modifying any input."""
    issues: list[str] = []
    active = project_snapshot or {}
    active_frames = active.get("frames")
    if isinstance(active_frames, list):
        if [normalize_frame(frame) for frame in active_frames] != [
            normalize_frame(frame) for frame in frame_projection
        ]:
            issues.append("frames_projection_mismatch")
    elif frame_projection:
        issues.append("active_snapshot_missing_frames")

    if current_version_id is None:
        return issues
    if current_version_snapshot is None:
        issues.append("current_version_missing")
        return issues

    expected = str(current_version_id)
    if active != current_version_snapshot:
        issues.append("active_snapshot_differs_from_current_version")
    active_ref = snapshot_reference_version(active)
    if has_frames_module(active) and active_ref is None:
        issues.append("active_artifact_ref_missing")
    elif active_ref not in {None, expected}:
        issues.append("active_artifact_ref_mismatch")
    version_ref = snapshot_reference_version(current_version_snapshot)
    if has_frames_module(current_version_snapshot) and version_ref is None:
        issues.append("version_artifact_ref_missing")
    elif version_ref not in {None, expected}:
        issues.append("version_artifact_ref_mismatch")
    return issues


def repair_snapshot_reference(
    snapshot: dict[str, Any], version_id: uuid.UUID
) -> dict[str, Any]:
    """Idempotently bind a Frames module payload/reference to its owning version."""
    return compact_frames_artifact_reference(snapshot, version_id)
