"""Deterministic state compiler for array-sorting lessons.

The model supplies narration, frame titles and visual emphasis.  When an
authoritative input array is available, this module supplies every executable
array state so a model cannot invent an intermediate or final permutation.
"""

from __future__ import annotations

import ast
import json
import re
from copy import deepcopy
from numbers import Real
from typing import Any

_SORT_MARKERS = {
    "insertion_sort": ("insertion sort", "插入排序"),
    "bubble_sort": ("bubble sort", "冒泡排序"),
    "selection_sort": ("selection sort", "选择排序"),
    "merge_sort": ("merge sort", "归并排序"),
    "quick_sort": ("quick sort", "quicksort", "快速排序"),
}


def _algorithm(dsl: dict[str, Any]) -> str | None:
    text = " ".join(
        [str(dsl.get("topic", ""))]
        + [
            str(frame.get(key, ""))
            for frame in dsl.get("frames", [])
            if isinstance(frame, dict)
            for key in ("title", "narration")
        ]
    ).casefold()
    for name, markers in _SORT_MARKERS.items():
        if any(marker in text for marker in markers):
            return name
    return None


def _usable_values(value: Any) -> list[Any] | None:
    if not isinstance(value, list) or not value or len(value) > 64:
        return None
    if any(isinstance(item, (dict, list, tuple, set)) or item is None for item in value):
        return None
    if not all(isinstance(item, (str, Real)) and not isinstance(item, bool) for item in value):
        return None
    return deepcopy(value)


def _values_from_mapping(value: Any) -> list[Any] | None:
    if not isinstance(value, dict):
        return _usable_values(value)
    for key in ("values", "array", "items", "data"):
        candidate = _usable_values(value.get(key))
        if candidate is not None:
            return candidate
    return None


def _extract_input(dsl: dict[str, Any], algorithm_input: Any) -> tuple[list[Any] | None, str]:
    candidate = _values_from_mapping(algorithm_input)
    if candidate is not None:
        return candidate, "authoritative_algorithm_input"
    for key in ("algorithm_input", "input", "dataset_input"):
        candidate = _values_from_mapping(dsl.get(key))
        if candidate is not None:
            return candidate, f"dsl.{key}"
    # A literal in the user topic is an input declaration, not a model state
    # hint. Prefer it over any array the model may have hallucinated in a
    # frame snapshot.
    text = str(dsl.get("topic", ""))
    for match in re.finditer(r"\[[^\[\]]+\]", text):
        raw = match.group(0)
        for parser in (json.loads, ast.literal_eval):
            try:
                candidate = _usable_values(parser(raw))
            except (ValueError, SyntaxError, TypeError, json.JSONDecodeError):
                continue
            if candidate is not None:
                return candidate, "topic.array_literal"
    for frame in dsl.get("frames", []):
        if not isinstance(frame, dict):
            continue
        snapshot = frame.get("state_snapshot")
        if isinstance(snapshot, dict):
            for key in ("array", "values", "items"):
                candidate = _usable_values(snapshot.get(key))
                if candidate is not None:
                    return candidate, f"frame.{key}"
        for visual in frame.get("visual_objects", []):
            if not isinstance(visual, dict) or visual.get("type") != "array":
                continue
            cells = visual.get("cells", visual.get("values"))
            if isinstance(cells, list):
                values = [cell.get("value") if isinstance(cell, dict) else cell for cell in cells]
                candidate = _usable_values(values)
                if candidate is not None:
                    return candidate, "visual.array"
    return None, "unavailable"


def _sort_key(value: Any) -> tuple[int, Any]:
    if isinstance(value, Real) and not isinstance(value, bool):
        return 0, float(value)
    return 1, str(value)


def _ordered(values: list[Any]) -> list[Any]:
    return sorted(values, key=_sort_key)


def _state(array: list[Any], algorithm: str, phase: str, **metadata: Any) -> dict[str, Any]:
    return {
        "array": deepcopy(array),
        "sorting_algorithm": algorithm,
        "phase": phase,
        **metadata,
    }


def _insertion_states(values: list[Any]) -> list[dict[str, Any]]:
    work = list(values)
    states = [_state(work, "insertion_sort", "init", sorted_prefix=1)]
    for index in range(1, len(work)):
        key = work[index]
        cursor = index - 1
        while cursor >= 0 and _sort_key(work[cursor]) > _sort_key(key):
            work[cursor + 1] = work[cursor]
            cursor -= 1
            states.append(_state(
                work, "insertion_sort", "shift", i=index, j=cursor, key=key,
                sorted_prefix=index,
            ))
        work[cursor + 1] = key
        states.append(_state(
            work, "insertion_sort", "insert", i=index, j=cursor + 1, key=key,
            sorted_prefix=index + 1,
        ))
    return states


def _bubble_states(values: list[Any]) -> list[dict[str, Any]]:
    work = list(values)
    states = [_state(work, "bubble_sort", "init", sorted_suffix=0)]
    n = len(work)
    for end in range(n - 1, 0, -1):
        swapped = False
        for index in range(end):
            if _sort_key(work[index]) > _sort_key(work[index + 1]):
                work[index], work[index + 1] = work[index + 1], work[index]
                swapped = True
                states.append(_state(
                    work, "bubble_sort", "swap", i=index, j=index + 1,
                    sorted_suffix=n - end,
                ))
        states.append(_state(
            work, "bubble_sort", "pass", pass_end=end,
            sorted_suffix=n - end + 1,
        ))
        if not swapped:
            break
    return states


def _selection_states(values: list[Any]) -> list[dict[str, Any]]:
    work = list(values)
    states = [_state(work, "selection_sort", "init", sorted_prefix=0)]
    for start in range(len(work) - 1):
        minimum = min(range(start, len(work)), key=lambda index: _sort_key(work[index]))
        if minimum != start:
            work[start], work[minimum] = work[minimum], work[start]
        states.append(_state(
            work, "selection_sort", "select", i=start, minimum=minimum,
            sorted_prefix=start + 1,
        ))
    return states


def _merge_states(values: list[Any]) -> list[dict[str, Any]]:
    work = list(values)
    states = [_state(work, "merge_sort", "init")]
    width = 1
    while width < len(work):
        for left in range(0, len(work), 2 * width):
            middle = min(left + width, len(work))
            right = min(left + 2 * width, len(work))
            work[left:right] = _ordered(work[left:right])
            states.append(_state(
                work, "merge_sort", "merge", left=left, middle=middle, right=right,
            ))
        width *= 2
    return states


def _quick_states(values: list[Any]) -> list[dict[str, Any]]:
    work = list(values)
    states = [_state(work, "quick_sort", "init")]

    def partition(left: int, right: int) -> int:
        pivot = work[right]
        boundary = left
        for index in range(left, right):
            if _sort_key(work[index]) <= _sort_key(pivot):
                if boundary != index:
                    work[boundary], work[index] = work[index], work[boundary]
                    states.append(_state(
                        work, "quick_sort", "swap", left=left, right=right,
                        pivot=pivot, i=boundary, j=index,
                    ))
                boundary += 1
        if boundary != right:
            work[boundary], work[right] = work[right], work[boundary]
        states.append(_state(
            work, "quick_sort", "partition", left=left, right=right,
            pivot=pivot, pivot_index=boundary,
        ))
        return boundary

    def sort(left: int, right: int) -> None:
        if left >= right:
            return
        pivot_index = partition(left, right)
        sort(left, pivot_index - 1)
        sort(pivot_index + 1, right)

    sort(0, len(work) - 1)
    return states


_STATE_BUILDERS = {
    "insertion_sort": _insertion_states,
    "bubble_sort": _bubble_states,
    "selection_sort": _selection_states,
    "merge_sort": _merge_states,
    "quick_sort": _quick_states,
}


def _compile_visual_array(visual: dict[str, Any], values: list[Any]) -> None:
    cells = visual.get("cells", visual.get("values", []))
    if not isinstance(cells, list):
        return
    output: list[dict[str, Any]] = []
    for index, value in enumerate(values):
        cell = deepcopy(cells[index]) if index < len(cells) and isinstance(cells[index], dict) else {}
        cell["index"] = index
        cell["value"] = value
        output.append(cell)
    visual["cells"] = output
    visual.pop("values", None)


def compile_sorting_trace(
    dsl: dict[str, Any], *, algorithm_input: Any = None
) -> dict[str, Any]:
    """Compile sorting state while preserving model-owned narration/visual cues."""
    if not isinstance(dsl, dict) or not isinstance(dsl.get("frames"), list):
        return dsl
    result = deepcopy(dsl)
    algorithm = _algorithm(result)
    if algorithm is None:
        return result
    values, source = _extract_input(result, algorithm_input)
    report: dict[str, Any] = {
        "applied": False,
        "algorithm": algorithm,
        "mode": "deterministic_sort_state_machine",
        "input_source": source,
        "frames_compiled": 0,
        "state_count": 0,
        "issues": [],
    }
    if values is None:
        report["status"] = "skipped_input_unavailable"
        result["sorting_trace_compilation"] = report
        return result
    states = _STATE_BUILDERS[algorithm](values)
    frames = result["frames"]
    if not frames:
        report["issues"].append("sorting artifact contains no frames")
        result["sorting_trace_compilation"] = report
        return result
    last_frame_index = max(1, len(frames) - 1)
    last_state_index = len(states) - 1
    for frame_index, frame in enumerate(frames):
        if not isinstance(frame, dict):
            continue
        state_index = min(
            last_state_index,
            int(frame_index * last_state_index / last_frame_index + 0.5),
        )
        expected = states[state_index]
        snapshot = deepcopy(frame.get("state_snapshot")) if isinstance(frame.get("state_snapshot"), dict) else {}
        snapshot["array"] = deepcopy(expected["array"])
        for alias in ("values", "items", "sorted_array"):
            if alias in snapshot:
                snapshot[alias] = deepcopy(expected["array"])
        for key in ("sorting_algorithm", "phase", "sorted_prefix", "sorted_suffix", "pass_end", "i", "j", "key", "minimum", "left", "middle", "right", "pivot", "pivot_index"):
            if key in expected:
                snapshot[key] = deepcopy(expected[key])
        frame["state_snapshot"] = snapshot
        for visual in frame.get("visual_objects", []):
            if isinstance(visual, dict) and visual.get("type") == "array":
                _compile_visual_array(visual, expected["array"])
        report["frames_compiled"] += 1
    report["state_count"] = len(states)
    report["applied"] = report["frames_compiled"] > 0
    result["sorting_trace_compilation"] = report
    return result


__all__ = ["compile_sorting_trace"]
