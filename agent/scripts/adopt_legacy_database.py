"""Safely adopt a compatible pre-Alembic development database.

Dry-run is the default. ``--apply`` stamps only a verified baseline-compatible
schema at revision 0001, then upgrades it to the current head. Partial or
incompatible schemas are always rejected.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from config import get_settings

BASELINE_COLUMNS: dict[str, set[str]] = {
    "projects": {"id", "title", "status", "dsl_snapshot"},
    "frames": {"id", "project_id", "frame_id", "order_index"},
    "parameters": {"id", "project_id", "key", "param_type"},
    "quality_reports": {"id", "project_id", "version"},
    "export_jobs": {"id", "project_id", "target", "status"},
    "feedback": {"id", "project_id", "type", "content"},
    "source_materials": {"id", "project_id", "type"},
    "project_versions": {"id", "project_id", "version", "dsl_snapshot"},
    "knowledge_base": {"id", "concept", "embedding"},
}


def classify_schema(
    tables: set[str], columns: dict[str, set[str]]
) -> str:
    if "alembic_version" in tables:
        return "managed"
    present = set(BASELINE_COLUMNS) & tables
    if not present:
        return "empty"
    missing_tables = set(BASELINE_COLUMNS) - tables
    missing_columns = {
        table: required - columns.get(table, set())
        for table, required in BASELINE_COLUMNS.items()
        if table in tables and not required <= columns.get(table, set())
    }
    if missing_tables or missing_columns:
        details = []
        if missing_tables:
            details.append(f"missing tables: {', '.join(sorted(missing_tables))}")
        if missing_columns:
            encoded = "; ".join(
                f"{table}({', '.join(sorted(names))})"
                for table, names in sorted(missing_columns.items())
            )
            details.append(f"missing columns: {encoded}")
        raise RuntimeError("Incompatible partial legacy schema; " + "; ".join(details))
    return "legacy_baseline"


async def inspect_schema() -> tuple[set[str], dict[str, set[str]]]:
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            rows = (
                await connection.execute(
                    text(
                        "SELECT table_name, column_name FROM information_schema.columns "
                        "WHERE table_schema = 'public'"
                    )
                )
            ).all()
            table_rows = (
                await connection.execute(
                    text(
                        "SELECT tablename FROM pg_tables "
                        "WHERE schemaname = 'public'"
                    )
                )
            ).scalars().all()
    finally:
        await engine.dispose()
    columns: dict[str, set[str]] = {}
    for table, column in rows:
        columns.setdefault(str(table), set()).add(str(column))
    return {str(table) for table in table_rows}, columns


def _alembic_config() -> Config:
    agent_root = Path(__file__).resolve().parent.parent
    config = Config(str(agent_root / "alembic.ini"))
    config.set_main_option("script_location", str(agent_root / "alembic"))
    return config


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the verified stamp/upgrade; otherwise only inspect.",
    )
    args = parser.parse_args()
    tables, columns = asyncio.run(inspect_schema())
    state = classify_schema(tables, columns)
    print(f"database schema state: {state}")
    if not args.apply:
        print("dry-run only; pass --apply to migrate")
        return 0

    config = _alembic_config()
    if state == "legacy_baseline":
        print("compatible pre-Alembic schema detected; stamping revision 0001")
        command.stamp(config, "0001")
    command.upgrade(config, "head")
    print("database schema upgraded to Alembic head")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
