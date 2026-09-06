"""Application resource lifecycle tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_close_database_disposes_shared_engine():
    from db.database import close_database

    fake_engine = MagicMock()
    fake_engine.dispose = AsyncMock()
    with patch("db.database.engine", fake_engine):
        await close_database()

    fake_engine.dispose.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_close_export_resources_closes_and_clears_redis_client():
    import api.export as export_api

    client = MagicMock()
    export_api._redis_client = client

    await export_api.close_export_resources()

    client.close.assert_called_once_with()
    assert export_api._redis_client is None
