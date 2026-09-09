"""Artifact consistency audit and narrowly-scoped repair tests."""

import uuid

from services.artifact_consistency import (
    inspect_project_artifacts,
    repair_snapshot_reference,
)


def _frame(title: str = "frame") -> dict:
    return {"frame_id": "f_001", "title": title}


def test_clean_version_and_projection_have_no_issues():
    version_id = uuid.uuid4()
    snapshot = repair_snapshot_reference(
        {
            "frames": [_frame()],
            "module_outputs": {"frames": {"frames": [_frame()]}},
        },
        version_id,
    )

    assert inspect_project_artifacts(
        project_snapshot=snapshot,
        current_version_id=version_id,
        current_version_snapshot=snapshot,
        frame_projection=[_frame()],
    ) == []


def test_dirty_working_copy_only_checks_frame_projection():
    assert inspect_project_artifacts(
        project_snapshot={"frames": [_frame("edited")]},
        current_version_id=None,
        current_version_snapshot=None,
        frame_projection=[_frame("edited")],
    ) == []


def test_reports_pointer_snapshot_and_projection_drift():
    version_id = uuid.uuid4()
    old_version_id = uuid.uuid4()
    active = {
        "frames": [_frame("active")],
        "module_outputs": {
            "frames": {
                "artifact_ref": {
                    "type": "project_version_frames",
                    "version_id": str(old_version_id),
                }
            }
        },
    }
    version = repair_snapshot_reference(
        {
            "frames": [_frame("saved")],
            "module_outputs": {"frames": {"frames": [_frame("saved")]}},
        },
        version_id,
    )

    assert inspect_project_artifacts(
        project_snapshot=active,
        current_version_id=version_id,
        current_version_snapshot=version,
        frame_projection=[_frame("row")],
    ) == [
        "frames_projection_mismatch",
        "active_snapshot_differs_from_current_version",
        "active_artifact_ref_mismatch",
    ]


def test_reference_repair_is_idempotent_and_rebinds():
    first_id = uuid.uuid4()
    second_id = uuid.uuid4()
    source = {
        "frames": [_frame()],
        "module_outputs": {"frames": {"frames": [_frame()]}},
    }
    first = repair_snapshot_reference(source, first_id)
    second = repair_snapshot_reference(first, second_id)

    assert second == repair_snapshot_reference(second, second_id)
    assert second["module_outputs"]["frames"]["artifact_ref"][
        "version_id"
    ] == str(second_id)
    assert "frames" not in second["module_outputs"]["frames"]


def test_reports_legacy_duplicate_as_missing_reference():
    version_id = uuid.uuid4()
    legacy = {
        "frames": [_frame()],
        "module_outputs": {"frames": {"frames": [_frame()]}},
    }

    assert inspect_project_artifacts(
        project_snapshot=legacy,
        current_version_id=version_id,
        current_version_snapshot=legacy,
        frame_projection=[_frame()],
    ) == [
        "active_artifact_ref_missing",
        "version_artifact_ref_missing",
    ]
