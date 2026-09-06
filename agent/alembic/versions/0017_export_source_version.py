"""bind export jobs to immutable project versions

Revision ID: 0017_export_source_version
Revises: 0016_observability_indexes
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0017_export_source_version"
down_revision: str | None = "0016_observability_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "export_jobs",
        sa.Column("source_version_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_export_jobs_source_version",
        "export_jobs",
        "project_versions",
        ["source_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_export_jobs_source_version",
        "export_jobs",
        ["source_version_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_export_jobs_source_version", table_name="export_jobs")
    op.drop_constraint(
        "fk_export_jobs_source_version",
        "export_jobs",
        type_="foreignkey",
    )
    op.drop_column("export_jobs", "source_version_id")
