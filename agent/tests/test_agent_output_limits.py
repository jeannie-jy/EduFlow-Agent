"""Deterministic bounds applied after structured Agent responses."""

from agents.nodes import (
    _bounded_coder_output,
    _bounded_knowledge_graph,
    _bounded_teaching_plan,
)


def test_teaching_plan_is_bounded_before_next_node():
    plan = _bounded_teaching_plan({
        "objectives": [f"objective-{i}" for i in range(10)],
        "outline": [
            {
                "step": 99,
                "title": "x" * 500,
                "key_points": [f"point-{i}" for i in range(10)],
                "estimated_frames": 99,
            }
            for _ in range(10)
        ],
        "estimated_total_frames": 99,
        "suggested_parameters": [{"key": "x"} for _ in range(10)],
    })

    assert len(plan["objectives"]) == 5
    assert len(plan["outline"]) == 8
    assert len(plan["outline"][0]["key_points"]) == 5
    assert len(plan["outline"][0]["title"]) == 120
    assert plan["outline"][0]["estimated_frames"] == 8
    assert plan["estimated_total_frames"] == 12
    assert len(plan["suggested_parameters"]) == 8


def test_knowledge_graph_is_bounded_before_coder_prompt():
    graph = _bounded_knowledge_graph({
        "concepts": [{"id": str(i), "name": "n"} for i in range(20)],
        "edges": [{"source": "a", "target": "b", "relation": "leads_to"} for _ in range(30)],
        "key_terms": [str(i) for i in range(20)],
    })

    assert len(graph["concepts"]) == 12
    assert len(graph["edges"]) == 24
    assert len(graph["key_terms"]) == 15


def test_coder_output_is_bounded_before_persistence():
    result = _bounded_coder_output({
        "frames": [
            {
                "frame_id": str(i),
                "narration": "n" * 500,
                "visual_objects": [{} for _ in range(8)],
                "animations": [{} for _ in range(8)],
            }
            for i in range(20)
        ],
        "parameters": [{} for _ in range(20)],
        "assets": [{} for _ in range(20)],
    })

    assert len(result["frames"]) == 12
    assert len(result["frames"][0]["narration"]) == 360
    assert len(result["frames"][0]["visual_objects"]) == 4
    assert len(result["frames"][0]["animations"]) == 6
    assert len(result["parameters"]) == 8
    assert len(result["assets"]) == 12
