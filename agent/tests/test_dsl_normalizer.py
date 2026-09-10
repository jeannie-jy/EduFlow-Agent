from __future__ import annotations

from pydantic import ValidationError

from schema.dsl import RenderScript
from schema.algorithm_trace import AlgorithmState
from tools.normalize_dsl import normalize_dsl


def _legacy_dsl() -> dict:
    return {
        "project_id": "normalizer-test",
        "topic": "测试排序",
        "audience": "undergraduate_cs_advanced",
        "difficulty": "intermediate",
        "parameters": [
            {
                "key": "values",
                "label": "数组",
                "type": "list",
                "visibility": "visible",
                "recompute_scope": "all",
            },
        ],
        "frames": [
            {
                "frame_id": "f_001",
                "title": "引入",
                "narration": "展示待排序数组",
                "visual_objects": [
                    {"id": "text_1", "type": "text", "label": "说明", "content": {"value": "开始"}},
                    {"id": "code_1", "type": "code_block", "language": "pseudocode", "code": "compare"},
                ],
                "state_snapshot": {"array": [2, 1]},
                "animations": [{"type": "show", "target": "text_1"}],
                "interaction_hooks": [
                    {
                        "type": "choice",
                        "parameter": {"key": "values"},
                        "options": [{"label": "比较", "value": "compare"}],
                    },
                ],
                "checks": [{"type": "sort_check", "expected": [1, 2]}],
            },
        ],
        "assets": [],
        "export_targets": ["web", "manim_video"],
    }


def test_normalize_dsl_canonicalizes_legacy_aliases():
    source = _legacy_dsl()
    normalized = normalize_dsl(source)

    assert source == _legacy_dsl(), "normalization must not mutate the input"
    assert normalized["audience"] == "undergraduate_cs"
    assert normalized["parameters"][0]["param_type"] == "array"
    assert normalized["parameters"][0]["visibility"] == "student"
    assert normalized["parameters"][0]["recompute_scope"] == "all_frames"
    assert normalized["frames"][0]["visual_objects"][0]["type"] == "card"
    assert normalized["frames"][0]["visual_objects"][1]["language"] == "text"
    assert normalized["frames"][0]["animations"][0]["type"] == "appear"
    assert normalized["frames"][0]["interaction_hooks"][0]["type"] == "select"
    assert normalized["frames"][0]["interaction_hooks"][0]["param"] == "values"
    assert normalized["frames"][0]["checks"][0]["type"] == "invariant"
    assert normalized["frames"][0]["checks"][0]["rule"] == '{"expected": [1, 2]}'

    RenderScript.model_validate(normalized)


def test_normalize_dsl_does_not_hide_missing_required_frame_id():
    source = _legacy_dsl()
    source["frames"][0].pop("frame_id")
    normalized = normalize_dsl(source)

    try:
        RenderScript.model_validate(normalized)
    except ValidationError as exc:
        assert "frame_id" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("missing frame_id must remain a blocking schema error")


def test_normalize_dsl_preserves_chart_as_renderable_table_or_card():
    source = _legacy_dsl()
    source["frames"][0]["visual_objects"] = [
        {"id": "chart_data", "type": "chart", "data": [1, 2, 3]},
        {"id": "chart_without_data", "type": "chart", "label": "趋势说明"},
    ]

    normalized = normalize_dsl(source)
    objects = normalized["frames"][0]["visual_objects"]

    assert objects[0]["type"] == "table"
    assert objects[0]["headers"] == ["value"]
    assert objects[0]["rows"] == [[1], [2], [3]]
    assert objects[1]["type"] == "card"
    assert objects[1]["content"] == "趋势说明"
    RenderScript.model_validate(normalized)


def test_normalize_dsl_canonicalizes_scalar_empty_queue_sentinels():
    source = _legacy_dsl()
    source["frames"][0]["state_snapshot"].update({
        "queue": "空队列",
        "priority_queue": "empty",
        "heap": "[]",
        "unvisited": "null",
    })

    normalized = normalize_dsl(source)
    snapshot = normalized["frames"][0]["state_snapshot"]

    assert snapshot["queue"] == []
    assert snapshot["priority_queue"] == []
    assert snapshot["heap"] == []
    assert snapshot["unvisited"] == []
    assert source["frames"][0]["state_snapshot"]["priority_queue"] == "empty"


def test_normalize_dsl_repairs_array_cells_and_preserves_quiz_content():
    source = _legacy_dsl()
    source["frames"][0]["visual_objects"] = [
        {"id": "arr", "type": "array", "cells": [3, 1, 2]},
        {
            "id": "quiz_1",
            "type": "quiz",
            "question": "下一步选择哪个元素？",
            "options": ["1", "2", "3"],
        },
    ]

    normalized = normalize_dsl(source)
    objects = normalized["frames"][0]["visual_objects"]

    assert objects[0]["cells"] == [
        {"index": 0, "value": 3},
        {"index": 1, "value": 1},
        {"index": 2, "value": 2},
    ]
    assert objects[1]["type"] == "card"
    assert "下一步选择哪个元素" in objects[1]["content"]
    assert "options" in objects[1]["content"]
    RenderScript.model_validate(normalized)


def test_normalize_dsl_uses_versioned_algorithm_trace_queue_contract():
    source = _legacy_dsl()
    source["topic"] = "用逐帧方式讲解 Dijkstra 最短路径算法"
    source["frames"][0]["state_snapshot"] = {
        "distances": {"s": 0, "C": 8},
        "processed": ["s"],
        "priority_queue": [["C", 8], "A(3)"],
    }

    normalized = normalize_dsl(source)
    snapshot = normalized["frames"][0]["state_snapshot"]

    assert snapshot["schema_version"] == "algorithm-trace-v1"
    assert snapshot["algorithm"] == "dijkstra"
    assert snapshot["dist"] == {"s": 0, "C": 8}
    assert snapshot["visited"] == ["s"]
    assert snapshot["queue"] == [
        {"vertex": "C", "priority": 8},
        {"vertex": "A", "priority": "3"},
    ]
    assert "priority_queue" not in snapshot
    report = normalized["normalization_report"]
    assert report["applied"] is True
    assert "queue_entries_to_objects" in report["repair_types"]
    AlgorithmState.model_validate(snapshot)
