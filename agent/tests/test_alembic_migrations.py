from pathlib import Path


def test_alembic_env_uses_async_engine() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "alembic" / "env.py"
    ).read_text(encoding="utf-8")
    assert "async_engine_from_config" in source
    assert "asyncio.run(run_async_migrations())" in source
    assert "from sqlalchemy import engine_from_config" not in source
