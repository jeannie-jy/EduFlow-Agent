"""Alembic comparison policy for schema objects owned by the baseline DDL."""

from __future__ import annotations

from typing import Any


BASELINE_MANAGED_TABLES = frozenset(
    {
        "teaching_plans",
        "knowledge_base",
        "langgraph_checkpoints",
    }
)

def include_object(
    object_: Any,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: Any | None,
) -> bool:
    """Exclude baseline-only reflected objects from Alembic autogeneration."""
    if not reflected or compare_to is not None:
        return True

    if type_ == "table":
        return name not in BASELINE_MANAGED_TABLES

    table_name = getattr(getattr(object_, "table", None), "name", None)
    if table_name in BASELINE_MANAGED_TABLES:
        return False
    return True
