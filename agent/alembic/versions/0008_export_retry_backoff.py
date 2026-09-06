"""add export retry scheduling

Revision ID: 0008_export_retry_backoff
Revises: 0007_export_job_attempts
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_export_retry_backoff"
down_revision: str | None = "0007_export_job_attempts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_export_jobs_claimable", table_name="export_jobs")
    op.add_column(
        "export_jobs",
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "export_jobs",
        sa.Column(
            "failure_retryable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.create_index(
        "ix_export_jobs_claimable",
        "export_jobs",
        ["status", "next_attempt_at", "lease_expires_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_export_jobs_claimable", table_name="export_jobs")
    op.drop_column("export_jobs", "failure_retryable")
    op.drop_column("export_jobs", "next_attempt_at")
    op.create_index(
        "ix_export_jobs_claimable",
        "export_jobs",
        ["status", "lease_expires_at", "created_at"],
    )
