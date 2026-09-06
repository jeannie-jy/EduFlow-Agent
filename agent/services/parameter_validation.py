"""Validation and recompute-mode selection for DSL parameters."""

from __future__ import annotations

import json
from typing import Any


def _parameter_type(definition: dict[str, Any]) -> str:
    return str(definition.get("param_type") or definition.get("type") or "string")


def _validate_value(definition: dict[str, Any], value: Any) -> None:
    param_type = _parameter_type(definition)
    constraints = definition.get("constraints") or {}
    valid_type = {
        "boolean": lambda candidate: isinstance(candidate, bool),
        "number": lambda candidate: isinstance(candidate, (int, float)) and not isinstance(candidate, bool),
        "integer": lambda candidate: isinstance(candidate, int) and not isinstance(candidate, bool),
        "string": lambda candidate: isinstance(candidate, str),
        "enum": lambda candidate: isinstance(candidate, (str, int, float)) and not isinstance(candidate, bool),
        "array": lambda candidate: isinstance(candidate, list),
        "object": lambda candidate: isinstance(candidate, dict),
    }.get(param_type)
    if valid_type is None or not valid_type(value):
        raise ValueError("Parameter value has the wrong type")

    options = constraints.get("options")
    if isinstance(options, list) and value not in options:
        raise ValueError("Parameter value is not an allowed option")
    if param_type in {"number", "integer"}:
        if isinstance(constraints.get("min"), (int, float)) and value < constraints["min"]:
            raise ValueError("Parameter value is below the minimum")
        if isinstance(constraints.get("max"), (int, float)) and value > constraints["max"]:
            raise ValueError("Parameter value is above the maximum")
    if param_type == "array":
        if isinstance(constraints.get("min_length"), int) and len(value) < constraints["min_length"]:
            raise ValueError("Parameter array is too short")
        if isinstance(constraints.get("max_length"), int) and len(value) > constraints["max_length"]:
            raise ValueError("Parameter array is too long")


def validate_parameter_changes(
    definitions: list[dict[str, Any]],
    changed: dict[str, Any],
) -> str:
    """Validate an atomic change set and return ``local`` or ``all_frames``."""
    if not changed or len(changed) > 20:
        raise ValueError("Parameter changes must contain between 1 and 20 keys")
    try:
        encoded = json.dumps(changed, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("Parameter values must be JSON serializable") from exc
    if len(encoded.encode("utf-8")) > 16_384:
        raise ValueError("Parameter changes are too large")

    by_key = {
        str(definition.get("key")): definition
        for definition in definitions
        if isinstance(definition, dict) and definition.get("key")
    }
    selected = []
    for key, value in changed.items():
        definition = by_key.get(key)
        if definition is None:
            raise ValueError("Unknown parameter key")
        _validate_value(definition, value)
        selected.append(definition)

    return (
        "local"
        if all(definition.get("recompute_scope") == "local" for definition in selected)
        else "all_frames"
    )
