"""Deterministic parameter-to-frame impact analysis.

The LLM may declare dependencies in the DSL, but the runtime never trusts those
declarations as the sole safety boundary. Structured references are inferred as
a fallback and an unknown structural dependency conservatively expands to the
whole timeline.
"""

from __future__ import annotations

import re
from typing import Any


def _contains_reference(value: Any, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(
            _contains_reference(item, key) for item in value.values()
        )
    if isinstance(value, list):
        return any(_contains_reference(item, key) for item in value)
    if not isinstance(value, str):
        return False
    patterns = (
        rf"\$\{{\s*{re.escape(key)}\s*\}}",
        rf"\{{\{{\s*{re.escape(key)}\s*\}}\}}",
        rf"(?<![A-Za-z0-9_]){re.escape(key)}(?![A-Za-z0-9_])",
    )
    return any(re.search(pattern, value) for pattern in patterns)


def analyze_parameter_impact(
    definitions: list[dict[str, Any]],
    frames: list[dict[str, Any]],
    changed_keys: list[str],
    validation_mode: str,
) -> dict[str, Any]:
    """Return the exact preview used to select the regeneration scope.

    Structural frame state is cumulative, so a direct dependency invalidates
    that frame and every successor. Local parameters are applied without an LLM
    run. Missing dependency metadata fails closed to all frames.
    """
    ordered_frames = [frame for frame in frames if isinstance(frame, dict)]
    ordered_ids = [
        str(frame.get("frame_id")) for frame in ordered_frames if frame.get("frame_id")
    ]
    known_ids = set(ordered_ids)
    definitions_by_key = {
        str(definition.get("key")): definition
        for definition in definitions
        if isinstance(definition, dict) and definition.get("key")
    }
    normalized_keys = sorted(set(changed_keys))

    if validation_mode == "local":
        return {
            "mode": "local",
            "scope": None,
            "changed_keys": normalized_keys,
            "dependencies": {key: [] for key in normalized_keys},
            "direct_frame_ids": [],
            "affected_frame_ids": [],
            "protected_frame_ids": ordered_ids,
            "fallback_used": False,
            "reason": "变更仅影响本地渲染属性，无需调用 Agent 重算帧",
        }

    structural_keys = [
        key
        for key in normalized_keys
        if definitions_by_key.get(key, {}).get("recompute_scope") != "local"
    ]
    dependencies: dict[str, list[str]] = {}
    direct_ids: set[str] = set()

    for key in structural_keys:
        definition = definitions_by_key.get(key, {})
        declared = definition.get("affects_frame_ids") or []
        matched = {
            str(frame_id)
            for frame_id in declared
            if isinstance(frame_id, str) and frame_id in known_ids
        }
        for frame in ordered_frames:
            frame_id = str(frame.get("frame_id", ""))
            declared_keys = frame.get("depends_on_parameters") or []
            if isinstance(declared_keys, list) and key in declared_keys:
                matched.add(frame_id)
                continue
            structured_content = {
                field: frame.get(field)
                for field in (
                    "state_snapshot",
                    "visual_objects",
                    "animations",
                    "interaction_hooks",
                    "checks",
                )
            }
            if _contains_reference(structured_content, key):
                matched.add(frame_id)
        dependencies[key] = [
            frame_id for frame_id in ordered_ids if frame_id in matched
        ]
        direct_ids.update(matched)

    fallback_used = not direct_ids
    if fallback_used:
        affected_ids = ordered_ids
        scope = {"type": "all_frames", "frame_ids": []}
        mode = "all_frames"
        reason = "缺少可验证的参数依赖，按保守策略重算全部帧"
    else:
        first_index = min(ordered_ids.index(frame_id) for frame_id in direct_ids)
        affected_ids = ordered_ids[first_index:]
        if first_index == 0:
            scope = {"type": "all_frames", "frame_ids": []}
            mode = "all_frames"
        else:
            scope = {"type": "from_frame", "frame_ids": [ordered_ids[first_index]]}
            mode = "partial_frames"
        reason = "重算直接依赖参数的最早帧及其状态后继"

    affected = set(affected_ids)
    return {
        "mode": mode,
        "scope": scope,
        "changed_keys": normalized_keys,
        "dependencies": dependencies,
        "direct_frame_ids": [
            frame_id for frame_id in ordered_ids if frame_id in direct_ids
        ],
        "affected_frame_ids": affected_ids,
        "protected_frame_ids": [
            frame_id for frame_id in ordered_ids if frame_id not in affected
        ],
        "fallback_used": fallback_used,
        "reason": reason,
    }


def expand_module_impact(
    module_ids: list[str],
    module_dependencies: dict[str, list[str]],
    root_module_ids: list[str],
) -> dict[str, Any]:
    """Expand changed artifacts through the same dependency DAG as generation.

    The result is deterministic and bounded. Unknown modules remain visible in
    the graph with no inferred dependencies rather than being silently executed.
    """
    ordered_ids = list(dict.fromkeys(
        str(module_id) for module_id in [*root_module_ids, *module_ids]
        if module_id
    ))[:100]
    known = set(ordered_ids)
    dependencies = {
        module_id: list(dict.fromkeys(
            str(dependency)
            for dependency in module_dependencies.get(module_id, [])[:20]
            if dependency
        ))
        for module_id in ordered_ids
    }
    affected = {module_id for module_id in root_module_ids if module_id in known}
    changed = True
    while changed:
        changed = False
        for module_id in ordered_ids:
            if module_id not in affected and affected.intersection(dependencies[module_id]):
                affected.add(module_id)
                changed = True

    return {
        "module_dependencies": dependencies,
        "affected_module_ids": [
            module_id for module_id in ordered_ids if module_id in affected
        ],
    }
