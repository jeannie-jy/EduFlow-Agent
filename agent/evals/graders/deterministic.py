"""Deterministic, model-free graders for RenderScript artifacts."""

from __future__ import annotations

import json
import math
import re
from typing import Any

from evals.models import EvalCase
from tools.validate_dsl import (
    check_algorithm_invariants,
    check_state_consistency,
    validate_dsl_schema,
)


def _normalise(value: Any) -> str:
    text = (
        value
        if isinstance(value, str)
        else json.dumps(value, ensure_ascii=False, sort_keys=True)
    ).casefold()
    return re.sub(r"[\s\-_，。；：、,.!?！？:;]+", "", text)


def _get_path(value: dict[str, Any], path: str) -> Any:
    current: Any = value
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _values_equal(actual: Any, expected: Any) -> bool:
    if isinstance(actual, float) and isinstance(expected, (int, float)):
        return math.isclose(actual, float(expected), rel_tol=1e-6, abs_tol=1e-8)
    return actual == expected


def _reference_integrity(frames: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    issues: list[str] = []
    known_ids: set[str] = set()
    for frame in frames:
        objects = frame.get("visual_objects", [])
        frame_ids = {
            str(obj.get("id"))
            for obj in objects
            if isinstance(obj, dict) and obj.get("id")
        }
        visible_ids = known_ids | frame_ids
        for obj in objects:
            if not isinstance(obj, dict) or obj.get("type") != "edge":
                continue
            for field in ("source", "target"):
                reference = obj.get(field)
                if reference and str(reference) not in visible_ids:
                    issues.append(
                        f"{frame.get('frame_id', '?')} edge {obj.get('id', '?')} "
                        f"references missing {field}={reference}"
                    )
        known_ids.update(frame_ids)
    return not issues, issues


def _find_array(final_state: dict[str, Any]) -> list[Any] | None:
    for key in ("array", "values", "items", "data"):
        candidate = final_state.get(key)
        if isinstance(candidate, list):
            return candidate
    return None


def _grade_oracle(case: EvalCase, frames: list[dict[str, Any]]) -> tuple[bool | None, list[str]]:
    if case.oracle is None:
        return None, []
    if not frames:
        return False, ["oracle cannot run because artifact has no frames"]

    final_state = frames[-1].get("state_snapshot", {})
    if case.oracle.kind == "sorted_array":
        values = case.oracle.input.get("values", [])
        expected = case.oracle.expected if case.oracle.expected is not None else sorted(values)
        actual = _find_array(final_state)
        if actual != expected:
            return False, [f"sorted array mismatch: expected={expected!r}, actual={actual!r}"]
        return True, []

    issues = []
    expected_state = case.oracle.expected or case.expected.final_state
    for path, expected in expected_state.items():
        actual = _get_path(final_state, path)
        if not _values_equal(actual, expected):
            issues.append(f"final state mismatch at {path}: expected={expected!r}, actual={actual!r}")
    return not issues, issues


async def grade_artifact(case: EvalCase, artifact: dict[str, Any]) -> dict[str, Any]:
    """Grade one artifact without calling an LLM.

    Deterministic failures are blocking and cannot be overwritten by a future
    LLM-as-judge score.
    """

    schema = await validate_dsl_schema(artifact)
    frames = artifact.get("frames", []) if isinstance(artifact, dict) else []
    frame_ids = [frame.get("frame_id") for frame in frames if isinstance(frame, dict)]
    frame_ids_unique = len(frame_ids) == len(set(frame_ids))
    consistency = await check_state_consistency(frames)
    algorithm = await check_algorithm_invariants(frames, topic=case.topic)
    references_ok, reference_issues = _reference_integrity(frames)

    normalised = _normalise(artifact)
    concept_results = {
        concept: _normalise(concept) in normalised
        for concept in case.expected.required_concepts
    }
    required_count = len(concept_results)
    concept_coverage = (
        sum(concept_results.values()) / required_count if required_count else 1.0
    )

    forbidden_hits = [
        claim
        for claim in case.expected.forbidden_claims
        if _normalise(claim) in normalised
    ]
    frame_count_ok = case.expected.min_frames <= len(frames) <= case.expected.max_frames
    oracle_ok, oracle_issues = _grade_oracle(case, frames)

    metrics: dict[str, bool | float | int | None] = {
        "dsl_schema_pass": bool(schema["valid"]),
        "frame_id_uniqueness_pass": frame_ids_unique,
        "state_consistency_pass": bool(consistency["consistent"]),
        "algorithm_invariant_pass": bool(algorithm["consistent"]),
        "reference_integrity_pass": references_ok,
        "required_concept_coverage": round(concept_coverage, 4),
        "forbidden_claim_pass": not forbidden_hits,
        "frame_count": len(frames),
        "frame_count_pass": frame_count_ok,
        "oracle_pass": oracle_ok,
    }
    blocking_checks = [
        bool(metrics["dsl_schema_pass"]),
        frame_ids_unique,
        bool(metrics["state_consistency_pass"]),
        bool(metrics["algorithm_invariant_pass"]),
        bool(metrics["reference_integrity_pass"]),
        bool(metrics["forbidden_claim_pass"]),
        bool(metrics["frame_count_pass"]),
        concept_coverage == 1.0,
    ]
    if oracle_ok is not None:
        blocking_checks.append(oracle_ok)

    issues = [*schema.get("errors", []), *schema.get("warnings", [])]
    if not frame_ids_unique:
        issues.append("duplicate frame_id values are blocking")
    issues.extend(issue.get("description", str(issue)) for issue in consistency.get("issues", []))
    issues.extend(
        f"algorithm invariant: {issue.get('description', issue)}"
        for issue in algorithm.get("issues", [])
    )
    issues.extend(reference_issues)
    issues.extend(f"missing required concept: {name}" for name, found in concept_results.items() if not found)
    issues.extend(f"forbidden claim present: {claim}" for claim in forbidden_hits)
    if not frame_count_ok:
        issues.append(
            f"frame count {len(frames)} outside [{case.expected.min_frames}, {case.expected.max_frames}]"
        )
    issues.extend(oracle_issues)

    return {
        "case_id": case.case_id,
        "tags": case.tags,
        "passed": all(blocking_checks),
        "metrics": metrics,
        "issues": issues,
    }
