"""API startup schema guard tests."""

from unittest.mock import AsyncMock, patch

import pytest


def _session_context(*scalar_results):
    session = AsyncMock()
    session.scalar = AsyncMock(side_effect=scalar_results)
    context = AsyncMock()
    context.__aenter__.return_value = session
    return context


@pytest.mark.asyncio
async def test_schema_guard_accepts_current_revision():
    from services.schema_guard import assert_database_schema_current

    context = _session_context("alembic_version", "head-1")
    with (
        patch("db.database.async_session_factory", return_value=context),
        patch("services.schema_guard.expected_database_revision", return_value="head-1"),
    ):
        await assert_database_schema_current()


@pytest.mark.asyncio
async def test_schema_guard_rejects_unversioned_legacy_database():
    from services.schema_guard import assert_database_schema_current

    context = _session_context(None)
    with (
        patch("db.database.async_session_factory", return_value=context),
        patch("services.schema_guard.expected_database_revision", return_value="head-1"),
        pytest.raises(RuntimeError, match="adopt_legacy_database"),
    ):
        await assert_database_schema_current()


@pytest.mark.asyncio
async def test_schema_guard_rejects_stale_revision():
    from services.schema_guard import assert_database_schema_current

    context = _session_context("alembic_version", "old-head")
    with (
        patch("db.database.async_session_factory", return_value=context),
        patch("services.schema_guard.expected_database_revision", return_value="head-1"),
        pytest.raises(RuntimeError, match="alembic upgrade head"),
    ):
        await assert_database_schema_current()
