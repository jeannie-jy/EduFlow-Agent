from __future__ import annotations

from schema.dsl import RenderScript
from tools.finalize_dsl import finalize_dsl


def _dsl() -> dict:
    return {
        "project_id": "finalizer-test",
        "topic": "树结构",
        "audience": "undergraduate_cs",
        "difficulty": "intermediate",
        "frames": [
            {
                "frame_id": "f_001",
                "title": "概念",
                "narration": "介绍树的根节点。",
                "visual_objects": [],
                "state_snapshot": {},
                "animations": [],
                "interaction_hooks": [],
                "checks": [],
            },
        ],
        "parameters": [],
        "assets": [],
        "export_targets": ["web", "manim_video"],
    }


def test_frames_generator_schema_matches_render_script_mindmap_contract():
    from generators.frames_generator import FRAMES_OUTPUT_SCHEMA

    visual = FRAMES_OUTPUT_SCHEMA["properties"]["frames"]["items"]["properties"][
        "visual_objects"
    ]["items"]["properties"]

    assert visual["content"]["type"] == "string"
    assert visual["root"]["type"] == "object"
    assert visual["children"]["items"]["type"] == "object"


def test_finalize_dsl_keeps_valid_artifact_on_canonical_path():
    result = finalize_dsl(_dsl())

    assert result["frames"][0]["title"] == "概念"
    assert result["finalization_report"] == {
        "applied": False,
        "mode": "canonical",
        "initial_error_count": 0,
        "repair_types": [],
        "repair_count": 0,
        "schema_valid": True,
    }
    RenderScript.model_validate(result)


def test_finalize_dsl_replaces_only_invalid_frame_and_preserves_visible_text():
    source = _dsl()
    source["frames"].append({
        "frame_id": "f_002",
        "title": "非法树对象",
        "narration": "",
        "visual_objects": [{
            "id": "tree_1",
            "type": "tree",
            "label": "平衡二叉树",
            "nodes": ["root", "left"],
        }],
        "state_snapshot": {},
    })

    result = finalize_dsl(source)

    assert result["frames"][0]["visual_objects"] == []
    assert result["frames"][1]["visual_objects"] == []
    assert "平衡二叉树" in result["frames"][1]["narration"]
    assert result["finalization_report"]["mode"] == "targeted_fallback"
    assert "invalid_frame_to_text_fallback" in result["finalization_report"]["repair_types"]
    RenderScript.model_validate(result)

    finalized_again = finalize_dsl(result)
    assert finalized_again["finalization_report"] == result["finalization_report"]


def test_finalize_dsl_repairs_duplicate_ids_and_preserves_required_concepts():
    source = _dsl()
    source["frames"].append({
        "frame_id": "f_001",
        "title": "第二步",
        "narration": "继续讲解。",
        "visual_objects": [],
        "state_snapshot": {},
    })

    result = finalize_dsl(source, required_concepts=["时间复杂度"])

    assert [frame["frame_id"] for frame in result["frames"]] == ["f_001", "f_002"]
    assert "时间复杂度" in result["frames"][-1]["narration"]
    repairs = result["finalization_report"]["repair_types"]
    assert "frame_id_reassigned" in repairs
    assert "required_concepts_preserved" in repairs
    RenderScript.model_validate(result)


def test_finalize_dsl_strips_invalid_algorithm_extensions_without_fallback():
    source = _dsl()
    source["topic"] = "Bellman-Ford 负权边"
    source["frames"][0]["state_snapshot"] = {
        "algorithm": "bellman_ford",
        "phase": "round",
        "dist": {"A": 0, "B": 4},
        "visited": [],
        "queue": [],
        "predecessor": {"A": None, "B": "A"},
        "edge_scan": [
            {"source": "A", "target": "B", "weight": 4, "relaxed": False},
        ],
    }

    result = finalize_dsl(source)

    assert result["frames"][0]["state_snapshot"]["edge_scan"] == [
        {"source": "A", "target": "B", "weight": 4},
    ]
    assert result["finalization_report"]["mode"] == "canonical"
    RenderScript.model_validate(result)
