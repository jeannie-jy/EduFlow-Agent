"""Legacy pre-Alembic database adoption safety tests."""

import pytest

from scripts.adopt_legacy_database import BASELINE_COLUMNS, classify_schema


def _compatible_columns() -> dict[str, set[str]]:
    return {table: set(columns) for table, columns in BASELINE_COLUMNS.items()}


def test_empty_schema_is_not_stamped_as_legacy():
    assert classify_schema({"checkpoints"}, {}) == "empty"


def test_existing_alembic_database_is_managed():
    assert classify_schema({"alembic_version", "projects"}, {}) == "managed"


def test_complete_legacy_baseline_can_be_adopted_with_extra_columns():
    columns = _compatible_columns()
    columns["projects"].add("legacy_extra")
    assert classify_schema(set(columns), columns) == "legacy_baseline"


def test_partial_legacy_schema_is_rejected():
    columns = _compatible_columns()
    columns.pop("frames")
    with pytest.raises(RuntimeError, match="missing tables: frames"):
        classify_schema(set(columns), columns)


def test_legacy_schema_missing_required_column_is_rejected():
    columns = _compatible_columns()
    columns["projects"].remove("dsl_snapshot")
    with pytest.raises(RuntimeError, match=r"projects\(dsl_snapshot\)"):
        classify_schema(set(columns), columns)
