import re
import subprocess
import sys
from pathlib import Path

from sqlalchemy import BigInteger

from db.models import ExportJobModel, Feedback, SourceMaterial


def test_alembic_env_uses_async_engine() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "alembic" / "env.py"
    ).read_text(encoding="utf-8")
    assert "async_engine_from_config" in source
    assert "asyncio.run(run_async_migrations())" in source
    assert "from sqlalchemy import engine_from_config" not in source


def test_orm_metadata_preserves_legacy_bootstrap_schema() -> None:
    assert {"duration_ms", "total_frames"} <= set(ExportJobModel.__table__.c.keys())
    assert "metadata" in SourceMaterial.__table__.c
    assert isinstance(SourceMaterial.__table__.c.size_bytes.type, BigInteger)
    assert any(
        str(constraint.sqltext) == "rating BETWEEN 1 AND 5"
        for constraint in Feedback.__table__.constraints
        if hasattr(constraint, "sqltext")
    )


def test_baseline_sql_preserves_legacy_bootstrap_schema() -> None:
    agent_dir = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=agent_dir,
        check=True,
        capture_output=True,
        text=True,
    )

    def table_sql(table_name: str) -> str:
        match = re.search(
            rf"CREATE TABLE {table_name} \((.*?)\n\);",
            result.stdout,
            flags=re.DOTALL,
        )
        assert match is not None
        return match.group(1)

    export_jobs = table_sql("export_jobs")
    assert "duration_ms INTEGER" in export_jobs
    assert "total_frames INTEGER" in export_jobs

    source_materials = table_sql("source_materials")
    assert "metadata JSONB" in source_materials
    assert "size_bytes BIGINT" in source_materials

    assert "CHECK (rating BETWEEN 1 AND 5)" in table_sql("feedback")
