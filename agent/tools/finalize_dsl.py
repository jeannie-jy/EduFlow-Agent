"""Deterministic final boundary for model-produced RenderScript artifacts.

The model may propose lesson structure and presentation content, but callers
must never persist or grade an artifact that still violates the executable DSL
contract.  This module applies the canonical adapters and compilers, validates
the result, and replaces only irreparable frames with a renderable text frame.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from copy import deepcopy
from typing import Any

from schema.algorithm_trace import validate_algorithm_snapshot
from schema.dsl import (
    Asset,
    Frame,
    KnowledgeGraph,
    Parameter,
    RenderScript,
    TeachingStrategy,
)
from tools.algorithm_trace_compiler import compile_algorithm_trace
from tools.normalize_dsl import normalize_dsl
from tools.validate_dsl import stabilize_algorithm_trace


def _text(value: Any, default: str = "") -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return default
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        return str(value)


def _canonical_pipeline(
    dsl: dict[str, Any],
    *,
    algorithm_input: Any = None,
    compile_sorting: bool = True,
) -> dict[str, Any]:
    result = normalize_dsl(dsl)
    result = stabilize_algorithm_trace(result)
    return compile_algorithm_trace(
        result,
        algorithm_input=algorithm_input,
        compile_sorting=compile_sorting,
    )


def _validation_errors(dsl: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    try:
        RenderScript.model_validate(dsl)
    except Exception as exc:  # Pydantic owns the nested error formatting.
        errors.append(str(exc))

    frames = dsl.get("frames", [])
    if not isinstance(frames, list):
        return [*errors, "frames must be an array"]
    frame_ids: list[str] = []
    for index, frame in enumerate(frames):
        if not isinstance(frame, dict):
            errors.append(f"frame[{index}] must be an object")
            continue
        frame_id = _text(frame.get("frame_id")).strip()
        if not frame_id:
            errors.append(f"frame[{index}] is missing frame_id")
        else:
            frame_ids.append(frame_id)
        errors.extend(
            f"frame[{index}] algorithm trace: {error}"
            for error in validate_algorithm_snapshot(frame.get("state_snapshot"))
        )
    if len(frame_ids) != len(set(frame_ids)):
        errors.append("frame_id values must be unique")
    return errors


_VISIBLE_TEXT_KEYS = {
    "title",
    "label",
    "name",
    "content",
    "text",
    "code",
    "latex",
    "question",
    "description",
}


def _visible_fragments(value: Any, *, limit: int = 12) -> list[str]:
    fragments: list[str] = []

    def visit(item: Any, key: str | None = None) -> None:
        if len(fragments) >= limit:
            return
        if isinstance(item, str):
            text = " ".join(item.split()).strip()
            if text and (key in _VISIBLE_TEXT_KEYS or key is None):
                fragments.append(text[:240])
            return
        if isinstance(item, list):
            for child in item[:16]:
                visit(child, key)
            return
        if isinstance(item, dict):
            for child_key, child in list(item.items())[:24]:
                visit(child, str(child_key))

    visit(value)
    return fragments


def _next_frame_id(index: int, used: set[str]) -> str:
    number = index + 1
    while (candidate := f"f_{number:03d}") in used:
        number += 1
    return candidate


def _safe_frame(value: Any, *, index: int, frame_id: str) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    title = _text(source.get("title"), f"步骤 {index + 1}").strip() or f"步骤 {index + 1}"
    narration = _text(source.get("narration")).strip()
    fragments = _visible_fragments(source.get("visual_objects", []))
    preserved = [fragment for fragment in fragments if fragment not in narration]
    if preserved:
        suffix = "；".join(preserved)
        narration = f"{narration}\n关键内容：{suffix}".strip()
    if not narration:
        narration = f"本帧介绍：{title}。"
    return {
        "frame_id": frame_id,
        "title": title,
        "learning_goal": _text(source.get("learning_goal"), title),
        "narration": narration[:2400],
        "visual_objects": [],
        "state_snapshot": {},
        "animations": [],
        "interaction_hooks": [],
        "checks": [],
        "depends_on_parameters": [],
    }


def _model_accepts(model: Any, value: Any) -> bool:
    try:
        model.model_validate(value)
    except Exception:
        return False
    return True


def _sanitize_root(result: dict[str, Any], repairs: list[str]) -> None:
    project_id = _text(result.get("project_id"), "generated-project").strip()
    topic = _text(result.get("topic"), "教学主题").strip()
    if result.get("project_id") != project_id:
        repairs.append("project_id_to_string")
    if result.get("topic") != topic:
        repairs.append("topic_to_string")
    result["project_id"] = project_id or "generated-project"
    result["topic"] = topic or "教学主题"

    for field, model, default in (
        ("teaching_strategy", TeachingStrategy, {}),
        ("knowledge_graph", KnowledgeGraph, {}),
    ):
        if not _model_accepts(model, result.get(field, default)):
            original = result.get(field)
            replacement = deepcopy(default)
            if field == "knowledge_graph" and isinstance(original, dict):
                sources = original.get("sources")
                if isinstance(sources, list):
                    replacement["sources"] = deepcopy(sources)
            result[field] = replacement
            repairs.append(f"invalid_{field}_to_default")

    for field, model in (("parameters", Parameter), ("assets", Asset)):
        raw_items = result.get(field, [])
        items = raw_items if isinstance(raw_items, list) else []
        accepted = [item for item in items if _model_accepts(model, item)]
        if accepted != raw_items:
            repairs.append(f"invalid_{field}_removed")
        result[field] = accepted

    raw_targets = result.get("export_targets", ["web", "manim_video"])
    targets = (
        [target for target in raw_targets if target in {"web", "manim_video"}]
        if isinstance(raw_targets, list)
        else []
    )
    if not targets:
        targets = ["web", "manim_video"]
    if targets != raw_targets:
        repairs.append("export_targets_to_supported")
    result["export_targets"] = targets


def _sanitize_frames(result: dict[str, Any], repairs: list[str]) -> None:
    raw_frames = result.get("frames", [])
    frames = raw_frames if isinstance(raw_frames, list) else []
    if not frames:
        frames = [{}]
        repairs.append("empty_frames_to_fallback")

    used: set[str] = set()
    sanitized: list[dict[str, Any]] = []
    for index, raw_frame in enumerate(frames):
        frame = deepcopy(raw_frame) if isinstance(raw_frame, dict) else {}
        requested_id = _text(frame.get("frame_id")).strip()
        frame_id = requested_id
        if not frame_id or frame_id in used:
            frame_id = _next_frame_id(index, used)
            repairs.append("frame_id_reassigned")
        frame["frame_id"] = frame_id
        used.add(frame_id)

        frame_errors = validate_algorithm_snapshot(frame.get("state_snapshot"))
        if not _model_accepts(Frame, frame) or frame_errors:
            frame = _safe_frame(raw_frame, index=index, frame_id=frame_id)
            repairs.append("invalid_frame_to_text_fallback")
        sanitized.append(frame)
    result["frames"] = sanitized


def _ensure_required_concepts(
    result: dict[str, Any],
    required_concepts: Iterable[str],
    repairs: list[str],
) -> None:
    concepts = [str(value).strip() for value in required_concepts if str(value).strip()]
    if not concepts or not result.get("frames"):
        return
    visible = json.dumps(result["frames"], ensure_ascii=False, sort_keys=True).casefold()
    missing = [concept for concept in concepts if concept.casefold() not in visible]
    if not missing:
        return
    frame = result["frames"][-1]
    suffix = "、".join(missing)
    narration = _text(frame.get("narration")).rstrip()
    frame["narration"] = f"{narration}\n关键知识点：{suffix}。".strip()
    repairs.append("required_concepts_preserved")


def _minimal_artifact(
    source: dict[str, Any],
    *,
    required_concepts: Iterable[str],
) -> dict[str, Any]:
    source_frames = source.get("frames", [])
    count = max(1, len(source_frames) if isinstance(source_frames, list) else 1)
    frames = [
        _safe_frame(
            source_frames[index] if isinstance(source_frames, list) else {},
            index=index,
            frame_id=f"f_{index + 1:03d}",
        )
        for index in range(count)
    ]
    result = {
        "project_id": _text(source.get("project_id"), "generated-project") or "generated-project",
        "topic": _text(source.get("topic"), "教学主题") or "教学主题",
        "audience": "undergraduate_cs",
        "difficulty": "intermediate",
        "teaching_strategy": {},
        "knowledge_graph": {},
        "parameters": [],
        "frames": frames,
        "assets": [],
        "export_targets": ["web", "manim_video"],
    }
    repairs: list[str] = []
    _ensure_required_concepts(result, required_concepts, repairs)
    return result


def finalize_dsl(
    dsl: dict[str, Any],
    *,
    algorithm_input: Any = None,
    compile_sorting: bool = True,
    required_concepts: Iterable[str] = (),
) -> dict[str, Any]:
    """Return a schema-valid canonical artifact with an auditable report."""
    source = deepcopy(dsl) if isinstance(dsl, dict) else {}
    previous_report = (
        source.get("finalization_report")
        if isinstance(source.get("finalization_report"), dict)
        else {}
    )
    result = _canonical_pipeline(
        source,
        algorithm_input=algorithm_input,
        compile_sorting=compile_sorting,
    )
    initial_errors = _validation_errors(result)
    repairs: list[str] = []
    mode = "canonical"

    if initial_errors:
        _sanitize_root(result, repairs)
        _sanitize_frames(result, repairs)
        _ensure_required_concepts(result, required_concepts, repairs)
        result = _canonical_pipeline(
            result,
            algorithm_input=algorithm_input,
            compile_sorting=compile_sorting,
        )
        mode = "targeted_fallback"

    final_errors = _validation_errors(result)
    if final_errors:
        result = _minimal_artifact(source, required_concepts=required_concepts)
        repairs.append("artifact_to_minimal_fallback")
        mode = "artifact_fallback"
        final_errors = _validation_errors(result)
    if final_errors:  # pragma: no cover - the hard-coded minimal contract is invariant.
        raise RuntimeError(f"deterministic DSL fallback is invalid: {final_errors}")

    previous_repairs = previous_report.get("repair_types", [])
    combined_repairs = [
        *(
            [str(value) for value in previous_repairs]
            if isinstance(previous_repairs, list)
            else []
        ),
        *repairs,
    ]
    previous_count = previous_report.get("repair_count", 0)
    previous_errors = previous_report.get("initial_error_count", 0)
    result["finalization_report"] = {
        "applied": bool(previous_report.get("applied")) or bool(repairs),
        "mode": (
            mode
            if repairs or not previous_report
            else str(previous_report.get("mode", "canonical"))
        ),
        "initial_error_count": (
            int(previous_errors) if isinstance(previous_errors, int) else 0
        ) + len(initial_errors),
        "repair_types": sorted(set(combined_repairs)),
        "repair_count": (
            int(previous_count) if isinstance(previous_count, int) else 0
        ) + len(repairs),
        "schema_valid": True,
    }
    return result


__all__ = ["finalize_dsl"]
