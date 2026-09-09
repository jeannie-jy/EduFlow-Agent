"""Liveness and dependency-aware readiness tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_readiness_reports_all_required_dependencies():
    import main

    session = AsyncMock()
    context = AsyncMock()
    context.__aenter__.return_value = session
    redis = MagicMock()
    redis.ping.return_value = True
    artifact_store = MagicMock()
    artifact_store.ready = AsyncMock()
    with (
        patch("db.database.async_session_factory", return_value=context),
        patch("api.export._get_redis", new=AsyncMock(return_value=redis)),
        patch(
            "services.artifact_store.get_artifact_store",
            return_value=artifact_store,
        ),
    ):
        checks = await main.readiness_checks()
    assert checks == {"database": "ok", "redis": "ok", "artifact_store": "ok"}


@pytest.mark.asyncio
async def test_readiness_exposes_dependency_failure_without_raising():
    import main

    with (
        patch("db.database.async_session_factory", side_effect=ConnectionError("down")),
        patch("api.export._get_redis", new=AsyncMock(return_value=None)),
        patch(
            "services.artifact_store.get_artifact_store",
            side_effect=ConnectionError("down"),
        ),
    ):
        checks = await main.readiness_checks()
    assert checks == {
        "database": "unavailable",
        "redis": "unavailable",
        "artifact_store": "unavailable",
    }
