"""add durable export worker lease fields

Revision ID: 0002_export_job_leases
Revises: 0001_baseline
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_export_job_leases"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "export_jobs",
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("export_jobs", sa.Column("worker_id", sa.String(length=200), nullable=True))
    op.add_column(
        "export_jobs",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_export_jobs_claimable",
        "export_jobs",
        ["status", "lease_expires_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_export_jobs_claimable", table_name="export_jobs")
    op.drop_column("export_jobs", "lease_expires_at")
    op.drop_column("export_jobs", "worker_id")
    op.drop_column("export_jobs", "attempt_count")
