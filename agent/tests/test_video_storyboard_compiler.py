from tools.compile_video_storyboard import compile_video_storyboard


def _dijkstra_dsl() -> dict:
    graph = {
        "id": "primary_graph",
        "type": "graph",
        "nodes": [{"id": "A"}, {"id": "B"}],
        "edges": [{"source": "A", "target": "B", "weight": 3}],
    }
    return {
        "topic": "Dijkstra 最短路径",
        "frames": [
            {
                "frame_id": "f_001",
                "title": "初始化",
                "narration": "从 A 出发。",
                "visual_objects": [
                    graph,
                    {"id": "code", "type": "code_block", "code": "dist[A] = 0"},
                ],
                "state_snapshot": {
                    "dist": {"A": 0, "B": None},
                    "predecessor": {"A": None, "B": None},
                    "visited": [],
                },
            },
            {
                "frame_id": "f_002",
                "title": "松弛 B",
                "narration": "通过 A 到达 B，距离更新为 3。",
                "visual_objects": [
                    graph,
                    {"id": "code", "type": "code_block", "code": "relax(A, B)"},
                ],
                "state_snapshot": {
                    "dist": {"A": 0, "B": 3},
                    "predecessor": {"A": None, "B": "A"},
                    "visited": ["A"],
                },
            },
        ],
    }


def test_graph_storyboard_removes_incidental_code_and_adds_state_panel():
    compiled = compile_video_storyboard(_dijkstra_dsl())

    for frame in compiled["frames"]:
        assert [obj["type"] for obj in frame["visual_objects"]] == ["graph", "table"]
        panel = frame["visual_objects"][1]
        assert panel["headers"] == ["节点", "距离", "前驱"]

    assert compiled["frames"][1]["video_transition"]["persistent_object_ids"] == [
        "primary_graph",
        "video_state_panel",
    ]
    assert "dist" in compiled["frames"][1]["video_transition"]["changed_state_keys"]
    assert compiled["video_storyboard_report"]["removed_code_blocks"] == 2
    assert compiled["video_storyboard_report"]["state_panels_added"] == 2


def test_explicit_implementation_lesson_keeps_only_bounded_code_scenes():
    dsl = _dijkstra_dsl()
    dsl["topic"] = "用 Python 实现 Dijkstra"
    for frame in dsl["frames"]:
        frame["learning_goal"] = "讲解代码实现"

    compiled = compile_video_storyboard(dsl)

    code_counts = [
        sum(obj["type"] == "code_block" for obj in frame["visual_objects"])
        for frame in compiled["frames"]
    ]
    assert code_counts == [1, 0]
    assert compiled["video_storyboard_report"]["code_scene_count"] == 1


def test_lone_code_object_is_not_removed_into_a_blank_scene():
    compiled = compile_video_storyboard({
        "topic": "算法概览",
        "frames": [{
            "frame_id": "f_001",
            "title": "步骤",
            "narration": "解释步骤。",
            "visual_objects": [{"id": "code", "type": "code_block", "code": "step()"}],
            "state_snapshot": {},
        }],
    })

    assert compiled["frames"][0]["visual_objects"][0]["type"] == "code_block"
