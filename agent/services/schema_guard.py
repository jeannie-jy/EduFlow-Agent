"""Fail-fast database schema checks for API startup."""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text


def expected_database_revision() -> str:
    agent_root = Path(__file__).resolve().parent.parent
    config = Config(str(agent_root / "alembic.ini"))
    config.set_main_option("script_location", str(agent_root / "alembic"))
    head = ScriptDirectory.from_config(config).get_current_head()
    if head is None:
        raise RuntimeError("Alembic migration head is missing")
    return head


async def assert_database_schema_current() -> None:
    """Refuse to serve requests against an absent or stale Alembic schema."""
    from db.database import async_session_factory

    expected = expected_database_revision()
    async with async_session_factory() as session:
        version_table = await session.scalar(
            text("SELECT to_regclass('public.alembic_version')")
        )
        if version_table is None:
            raise RuntimeError(
                "Database has no Alembic revision. Run "
                "`python -m scripts.adopt_legacy_database --apply` before starting the API."
            )
        current = await session.scalar(text("SELECT version_num FROM alembic_version"))
    if current != expected:
        raise RuntimeError(
            f"Database schema is at {current or 'no revision'}, expected {expected}. "
            "Run `alembic upgrade head` before starting the API."
        )
