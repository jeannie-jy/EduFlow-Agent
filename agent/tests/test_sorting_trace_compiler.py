from __future__ import annotations

from tools.algorithm_trace_compiler import compile_algorithm_trace
from tools.validate_dsl import check_sorting_invariants


def _dsl(topic: str, frame_count: int = 5) -> dict:
    return {
        "project_id": "sorting-compiler-test",
        "topic": topic,
        "frames": [
            {
                "frame_id": f"f_{index:03d}",
                "title": f"第 {index} 步",
                "narration": "保留模型生成的讲解与视觉提示。",
                "visual_objects": [
                    {
                        "id": "array-view",
                        "type": "array",
                        "cells": [{"index": 0, "value": "model-state"}],
                    }
                ],
                "state_snapshot": {"array": [999, 999, 999]},
            }
            for index in range(1, frame_count + 1)
        ],
    }


def test_insertion_sort_compiler_uses_authoritative_input_and_preserves_prompts():
    dsl = _dsl("使用数组 [4,3,2,1] 演示插入排序")
    dsl["frames"][0]["narration"] = "插入排序维护已排序区间，移动元素后插入当前值。"
    compiled = compile_algorithm_trace(
        dsl,
        algorithm_input={"values": [4, 3, 2, 1]},
    )

    report = compiled["sorting_trace_compilation"]
    assert report["applied"] is True
    assert report["input_source"] == "authoritative_algorithm_input"
    assert compiled["frames"][0]["state_snapshot"]["array"] == [4, 3, 2, 1]
    assert compiled["frames"][-1]["state_snapshot"]["array"] == [1, 2, 3, 4]
    assert compiled["frames"][0]["narration"].startswith("插入排序")
    assert [cell["value"] for cell in compiled["frames"][-1]["visual_objects"][0]["cells"]] == [1, 2, 3, 4]


def test_all_supported_sort_compilers_produce_sorted_terminal_state():
    cases = {
        "冒泡排序": "bubble_sort",
        "选择排序": "selection_sort",
        "归并排序": "merge_sort",
        "快速排序": "quick_sort",
    }
    for topic, algorithm in cases.items():
        compiled = compile_algorithm_trace(
            _dsl(topic),
            algorithm_input={"values": [5, 1, 4, 2, 3]},
        )
        report = compiled["sorting_trace_compilation"]
        assert report["algorithm"] == algorithm
        assert compiled["frames"][-1]["state_snapshot"]["array"] == [1, 2, 3, 4, 5]


def test_compiler_repairs_duplicated_model_element_and_syncs_visible_array():
    dsl = _dsl("冒泡排序", frame_count=3)
    dsl["frames"][0]["state_snapshot"]["array"] = [5, 3, 8, 1]
    dsl["frames"][0]["visual_objects"][0]["cells"] = [
        {"value": value} for value in [5, 3, 8, 1]
    ]
    dsl["frames"][1]["state_snapshot"]["array"] = [5, 5, 8, 1]
    dsl["frames"][1]["visual_objects"][0]["cells"] = [
        {"value": value} for value in [5, 5, 8, 1]
    ]

    compiled = compile_algorithm_trace(dsl)

    second_snapshot = compiled["frames"][1]["state_snapshot"]["array"]
    second_visible = [
        cell["value"]
        for cell in compiled["frames"][1]["visual_objects"][0]["cells"]
    ]
    assert sorted(second_snapshot) == [1, 3, 5, 8]
    assert second_visible == second_snapshot
    assert check_sorting_invariants(
        compiled["frames"], topic=compiled["topic"]
    )["consistent"] is True


def test_sorting_invariant_rejects_element_identity_drift():
    frames = [
        {
            "frame_id": "f_001",
            "state_snapshot": {"array": [5, 3, 8, 1]},
            "visual_objects": [{
                "id": "arr", "type": "array",
                "cells": [{"value": value} for value in [5, 3, 8, 1]],
            }],
        },
        {
            "frame_id": "f_002",
            "state_snapshot": {"array": [5, 5, 8, 1]},
            "visual_objects": [{
                "id": "arr", "type": "array",
                "cells": [{"value": value} for value in [5, 5, 8, 1]],
            }],
        },
    ]

    result = check_sorting_invariants(frames, topic="冒泡排序")

    assert result["consistent"] is False
    assert any("丢失、重复" in issue["description"] for issue in result["issues"])


def test_insertion_compiler_never_exposes_temporary_duplicate_values():
    compiled = compile_algorithm_trace(
        _dsl("插入排序", frame_count=8),
        algorithm_input={"values": [4, 3, 2, 1]},
    )

    for frame in compiled["frames"]:
        assert sorted(frame["state_snapshot"]["array"]) == [1, 2, 3, 4]
