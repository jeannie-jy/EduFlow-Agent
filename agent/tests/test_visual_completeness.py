from adapters.manim_adapter import ManimScriptGenerator
from tools.validate_dsl import check_visual_completeness, stabilize_algorithm_trace


def _graph(nodes, edges):
    return {
        "id": "primary_graph",
        "type": "graph",
        "graph_role": "primary",
        "nodes": nodes,
        "edges": edges,
    }


def test_bfs_uses_most_complete_topology_for_every_execution_frame():
    complete_nodes = [
        {"id": "A", "label": "A"},
        {"id": "B", "label": "B"},
        {"id": "C", "label": "C"},
    ]
    complete_edges = [
        {"source": "A", "target": "B", "directed": False},
        {"source": "A", "target": "C", "directed": False},
    ]
    dsl = {
        "topic": "BFS 广度优先搜索",
        "frames": [
            {
                "frame_id": "f_001",
                "visual_objects": [_graph([{"id": "A"}, {"id": "B"}], [])],
                "state_snapshot": {"algorithm": "bfs", "visited": ["A"]},
            },
            {
                "frame_id": "f_002",
                "visual_objects": [_graph(complete_nodes, complete_edges)],
                "state_snapshot": {"algorithm": "bfs", "visited": ["A", "B"]},
            },
        ],
    }

    stabilized = stabilize_algorithm_trace(dsl)
    graphs = [frame["visual_objects"][0] for frame in stabilized["frames"]]

    assert graphs[0]["nodes"] == complete_nodes
    assert graphs[0]["edges"] == complete_edges
    assert graphs[1]["nodes"] == complete_nodes
    assert graphs[1]["edges"] == complete_edges
    assert check_visual_completeness(stabilized["frames"])["complete"] is True


def test_visual_completeness_rejects_structural_shells_and_dangling_edges():
    frames = [{
        "frame_id": "f_bad",
        "visual_objects": [
            _graph([{"id": "A"}, {"id": "B"}], []),
            {"id": "arr", "type": "array", "cells": []},
            {"id": "table", "type": "table", "headers": [], "rows": []},
            {"id": "code", "type": "code_block", "code": "  "},
            {"id": "formula", "type": "formula", "latex": ""},
            {
                "id": "dangling",
                "type": "graph",
                "nodes": [{"id": "A"}],
                "edges": [{"source": "A", "target": "Z"}],
            },
        ],
    }]

    result = check_visual_completeness(frames)

    assert result["complete"] is False
    descriptions = " ".join(issue["description"] for issue in result["issues"])
    assert "缺少边" in descriptions
    assert "array 缺少 cells" in descriptions
    assert "table 缺少 headers 和 rows" in descriptions
    assert "code_block 缺少 code" in descriptions
    assert "formula 缺少 latex" in descriptions
    assert "Z" in descriptions


def test_visual_completeness_accepts_single_node_graph_and_populated_components():
    frames = [{
        "frame_id": "f_ok",
        "visual_objects": [
            _graph([{"id": "A"}], []),
            {"id": "arr", "type": "array", "cells": [{"value": 1}]},
            {"id": "table", "type": "table", "headers": ["key"], "rows": []},
            {"id": "code", "type": "code_block", "code": "return 1"},
            {"id": "formula", "type": "formula", "latex": "x + 1"},
        ],
    }]

    assert check_visual_completeness(frames) == {"complete": True, "issues": []}


def test_unimplemented_visual_type_falls_back_to_readable_semantic_panel():
    dsl = {
        "project_id": "fallback-panel",
        "topic": "树的遍历",
        "frames": [{
            "frame_id": "f_001",
            "title": "二叉树",
            "visual_objects": [{
                "id": "tree_demo",
                "type": "tree",
                "label": "二叉搜索树",
                "nodes": ["8", "3", "10"],
            }],
            "animations": [],
        }],
    }

    script = ManimScriptGenerator(dsl).generate()

    assert "tree_demo_0_box = RoundedRectangle" in script
    assert "Text('二叉搜索树'" in script
    assert '"nodes": ["8", "3", "10"]' in script
    assert "tree_demo_0 = Circle" not in script
    compile(script, "<generated-manim>", "exec")
