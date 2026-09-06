"""Deterministic partial-regeneration scope and merge tests."""

from __future__ import annotations

import pytest

from services.regeneration import (
    merge_scoped_dsl,
    normalize_regeneration_scope,
    resolve_target_frame_ids,
)


def _dsl() -> dict:
    return {
        "topic": "original",
        "parameters": [{"key": "speed", "current_value": 1}],
        "assets": [{"id": "asset-original"}],
        "frames": [
            {"frame_id": "f1", "title": "one"},
            {"frame_id": "f2", "title": "two"},
            {"frame_id": "f3", "title": "three"},
            {"frame_id": "f4", "title": "four"},
        ],
    }


@pytest.mark.parametrize(
    "scope",
    [
        {"type": "unknown", "frame_ids": []},
        {"type": "single_frame", "frame_ids": []},
        {"type": "single_frame", "frame_ids": ["f1", "f2"]},
        {"type": "from_frame", "frame_ids": ["f1", "f2"]},
        {"type": "frame_range", "frame_ids": ["f1"]},
        {"type": "frame_range", "frame_ids": ["f1", "f1"]},
        {"type": "single_frame", "frame_ids": [""]},
        {"type": "single_frame", "frame_ids": "f1"},
    ],
)
def test_normalize_rejects_invalid_scope(scope):
    with pytest.raises(ValueError):
        normalize_regeneration_scope(scope)


def test_normalize_all_frames_discards_irrelevant_ids():
    assert normalize_regeneration_scope(
        {"type": "all_frames", "frame_ids": ["f1"]}
    ) == {"type": "all_frames", "frame_ids": []}


def test_resolve_range_and_from_frame_are_order_aware():
    frames = _dsl()["frames"]
    assert resolve_target_frame_ids(
        frames, {"type": "frame_range", "frame_ids": ["f3", "f2"]}
    ) == {"f2", "f3"}
    assert resolve_target_frame_ids(
        frames, {"type": "from_frame", "frame_ids": ["f3"]}
    ) == {"f3", "f4"}


def test_single_frame_merge_preserves_outside_locked_and_non_frame_data():
    existing = _dsl()
    generated = {
        "topic": "must-not-overwrite",
        "parameters": [{"key": "speed", "current_value": 99}],
        "assets": [{"id": "asset-new"}],
        "frames": [{"frame_id": "f2", "title": "replacement"}],
    }
    merged = merge_scoped_dsl(
        existing,
        generated,
        {"type": "single_frame", "frame_ids": ["f2"]},
    )

    assert [frame["title"] for frame in merged["frames"]] == [
        "one", "replacement", "three", "four"
    ]
    assert merged["topic"] == "original"
    assert merged["parameters"] == existing["parameters"]
    assert merged["assets"] == existing["assets"]

    locked = merge_scoped_dsl(
        existing,
        generated,
        {"type": "single_frame", "frame_ids": ["f2"]},
        ["f2"],
    )
    assert locked == existing


def test_positional_replacements_keep_stable_ids_without_reusing_exact_match():
    merged = merge_scoped_dsl(
        _dsl(),
        {
            "frames": [
                {"frame_id": "f3", "title": "exact-three"},
                {"frame_id": "new-id", "title": "positional-two"},
            ]
        },
        {"type": "frame_range", "frame_ids": ["f2", "f3"]},
    )
    assert merged["frames"][1] == {"frame_id": "f2", "title": "positional-two"}
    assert merged["frames"][2] == {"frame_id": "f3", "title": "exact-three"}
