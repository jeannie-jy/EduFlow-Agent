"""Parameter validation and recompute routing tests."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest

from schema.project import RecomputeRequest
from services.parameter_dependencies import (
    analyze_parameter_impact,
    expand_module_impact,
)
from services.parameter_validation import validate_parameter_changes

DEFINITIONS = [
    {
        "key": "animation_speed",
        "param_type": "number",
        "constraints": {"min": 0.25, "max": 3},
        "recompute_scope": "local",
    },
    {
        "key": "input_size",
        "param_type": "integer",
        "constraints": {"min": 3, "max": 100},
        "recompute_scope": "all_frames",
    },
    {
        "key": "algorithm",
        "param_type": "enum",
        "constraints": {"options": ["a", "b"]},
        "recompute_scope": "all_frames",
    },
]


def test_validation_selects_local_or_full_recompute():
    assert validate_parameter_changes(DEFINITIONS, {"animation_speed": 2}) == "local"
    assert (
        validate_parameter_changes(DEFINITIONS, {"animation_speed": 2, "input_size": 8})
        == "all_frames"
    )


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"unknown": 1},
        {"animation_speed": True},
        {"animation_speed": 4},
        {"input_size": 2},
        {"input_size": 3.5},
        {"algorithm": "c"},
    ],
)
def test_validation_rejects_unknown_invalid_or_out_of_range_values(changes):
    with pytest.raises(ValueError):
        validate_parameter_changes(DEFINITIONS, changes)


def test_dependency_analysis_propagates_from_earliest_direct_frame():
    definitions = [dict(DEFINITIONS[1], affects_frame_ids=["f2"])]
    frames = [
        {"frame_id": "f1", "state_snapshot": {}},
        {
            "frame_id": "f2",
            "state_snapshot": {},
            "depends_on_parameters": ["input_size"],
        },
        {"frame_id": "f3", "state_snapshot": {}},
    ]

    impact = analyze_parameter_impact(definitions, frames, ["input_size"], "all_frames")

    assert impact["mode"] == "partial_frames"
    assert impact["scope"] == {"type": "from_frame", "frame_ids": ["f2"]}
    assert impact["direct_frame_ids"] == ["f2"]
    assert impact["affected_frame_ids"] == ["f2", "f3"]
    assert impact["protected_frame_ids"] == ["f1"]
    assert impact["fallback_used"] is False


def test_dependency_analysis_infers_structured_reference_and_fails_closed():
    frames = [
        {"frame_id": "f1", "state_snapshot": {}},
        {"frame_id": "f2", "state_snapshot": {"input_size": 8}},
    ]
    inferred = analyze_parameter_impact(
        [DEFINITIONS[1]], frames, ["input_size"], "all_frames"
    )
    fallback = analyze_parameter_impact(
        [DEFINITIONS[2]], frames, ["algorithm"], "all_frames"
    )

    assert inferred["scope"] == {"type": "from_frame", "frame_ids": ["f2"]}
    assert fallback["scope"] == {"type": "all_frames", "frame_ids": []}
    assert fallback["fallback_used"] is True


def test_module_impact_expands_transitively_from_frames():
    impact = expand_module_impact(
        ["mindmap", "frames", "video", "package"],
        {
            "mindmap": [],
            "frames": [],
            "video": ["frames"],
            "package": ["video"],
        },
        ["frames"],
    )

    assert impact["affected_module_ids"] == ["frames", "video", "package"]
    assert impact["module_dependencies"]["package"] == ["video"]


def test_module_impact_is_empty_for_local_parameter_changes():
    impact = expand_module_impact(
        ["frames", "video"],
        {"video": ["frames"]},
        [],
    )

    assert impact["affected_module_ids"] == []


def test_successful_module_regeneration_clears_its_stale_marker():
    from services.project_persistence import merge_dsl_snapshot

    merged = merge_dsl_snapshot(
        {
            "stale_module_ids": ["video", "quiz"],
            "module_outputs": {"video": {"status": "old"}},
        },
        module_outputs={"video": {"status": "completed"}},
    )

    assert merged["stale_module_ids"] == ["quiz"]
    assert merged["module_outputs"]["video"]["status"] == "completed"


def _session_with_project(parameters):
    project = SimpleNamespace(
        owner_id=None,
        current_version_id=None,
        dsl_snapshot={"parameters": parameters, "frames": [{"frame_id": "f1"}]},
    )
    session = MagicMock()
    session.get = AsyncMock(return_value=project)
    session.execute = AsyncMock()
    session.add = MagicMock()
    return session, project


@pytest.mark.asyncio
async def test_local_recompute_persists_without_starting_agent_stream():
    from api.parameters import recompute_project

    parameters = [dict(DEFINITIONS[0], current_value=1)]
    session, project = _session_with_project(parameters)
    with patch("api.versions.save_version", new=AsyncMock()) as save_version:
        response = await recompute_project(
            "11111111-1111-1111-1111-111111111111",
            RecomputeRequest(changed_params={"animation_speed": 2}),
            session,
        )

    assert response["mode"] == "local"
    assert response["stream_url"] is None
    assert response["affected_frame_ids"] == []
    assert project.dsl_snapshot["parameters"][0]["current_value"] == 2
    assert session.execute.await_count == 1
    save_version.assert_awaited_once()


@pytest.mark.asyncio
async def test_full_recompute_returns_explicit_all_frames_scope():
    from api.parameters import recompute_project

    parameters = [dict(DEFINITIONS[1], current_value=8)]
    session, project = _session_with_project(parameters)
    project.dsl_snapshot.update({
        "selected_modules": ["frames", "video"],
        "module_dependencies": {"frames": [], "video": ["frames"]},
        "module_outputs": {"video": {"status": "completed"}},
    })
    response = await recompute_project(
        "11111111-1111-1111-1111-111111111111",
        RecomputeRequest(changed_params={"input_size": 12}),
        session,
    )

    assert response["mode"] == "all_frames"
    assert response["affected_module_ids"] == ["frames", "video"]
    assert project.dsl_snapshot["stale_module_ids"] == ["video"]
    scope_json = parse_qs(urlparse(response["stream_url"]).query)["scope"][0]
    assert json.loads(scope_json) == {"type": "all_frames", "frame_ids": []}


@pytest.mark.asyncio
async def test_preview_returns_partial_scope_without_database_writes():
    from api.parameters import preview_recompute_project

    parameters = [dict(DEFINITIONS[1], current_value=8, affects_frame_ids=["f2"])]
    session, project = _session_with_project(parameters)
    project.dsl_snapshot["frames"] = [
        {"frame_id": "f1"},
        {"frame_id": "f2", "depends_on_parameters": ["input_size"]},
        {"frame_id": "f3"},
    ]

    response = await preview_recompute_project(
        "11111111-1111-1111-1111-111111111111",
        RecomputeRequest(changed_params={"input_size": 12}),
        session,
    )

    assert response["mode"] == "partial_frames"
    assert response["affected_frame_ids"] == ["f2", "f3"]
    assert session.execute.await_count == 0


@pytest.mark.asyncio
async def test_recompute_rejects_stale_impact_preview_before_database_writes():
    from api.parameters import recompute_project

    parameters = [dict(DEFINITIONS[1], current_value=8, affects_frame_ids=["f1"])]
    session, project = _session_with_project(parameters)

    with pytest.raises(Exception) as caught:
        await recompute_project(
            "11111111-1111-1111-1111-111111111111",
            RecomputeRequest(
                changed_params={"input_size": 12},
                expected_impact_token="stale-token",
            ),
            session,
        )

    assert getattr(caught.value, "status_code", None) == 409
    assert session.execute.await_count == 0
    assert project.dsl_snapshot["parameters"][0]["current_value"] == 8


@pytest.mark.asyncio
async def test_invalid_change_set_is_atomic_before_database_writes():
    from api.parameters import recompute_project

    session, project = _session_with_project([dict(DEFINITIONS[1], current_value=8)])
    with pytest.raises(Exception) as caught:
        await recompute_project(
            "11111111-1111-1111-1111-111111111111",
            RecomputeRequest(changed_params={"input_size": 2}),
            session,
        )

    assert getattr(caught.value, "status_code", None) == 422
    assert session.execute.await_count == 0
    assert project.dsl_snapshot["parameters"][0]["current_value"] == 8
