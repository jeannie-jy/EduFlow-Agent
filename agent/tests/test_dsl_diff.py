"""Semantic RenderScript version diff tests."""

from services.dsl_diff import diff_dsl_versions


def test_diff_reports_frame_parameter_metadata_and_order_changes():
    before = {
        "topic": "sorting",
        "frames": [
            {"frame_id": "f1", "title": "start", "state_snapshot": {"i": 0}},
            {"frame_id": "f2", "title": "compare", "state_snapshot": {"i": 1}},
            {"frame_id": "removed", "title": "old"},
        ],
        "parameters": [{"key": "size", "current_value": 4}],
    }
    after = {
        "topic": "stable sorting",
        "frames": [
            {"frame_id": "f2", "title": "compare", "state_snapshot": {"i": 2}},
            {"frame_id": "f1", "title": "start", "state_snapshot": {"i": 0}},
            {"frame_id": "added", "title": "done"},
        ],
        "parameters": [
            {"key": "size", "current_value": 8},
            {"key": "speed", "current_value": 1},
        ],
    }

    result = diff_dsl_versions(before, after)

    assert result["summary"] == {
        "frames_added": 1,
        "frames_removed": 1,
        "frames_modified": 1,
        "parameters_changed": 2,
        "metadata_fields_changed": 1,
        "frame_order_changed": True,
    }
    assert result["frames"]["modified"] == [
        {"frame_id": "f2", "changed_fields": ["state_snapshot"]}
    ]
    assert result["parameters"] == [
        {"key": "size", "change": "modified"},
        {"key": "speed", "change": "added"},
    ]


def test_diff_ignores_volatile_top_level_fields():
    result = diff_dsl_versions(
        {"artifact_version": "one", "frames": []},
        {"artifact_version": "two", "frames": []},
    )

    assert result["summary"]["metadata_fields_changed"] == 0
    assert result["frames"]["modified"] == []
