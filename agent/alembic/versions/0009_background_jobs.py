"""add durable background jobs

Revision ID: 0009_background_jobs
Revises: 0008_export_retry_backoff
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_background_jobs"
down_revision: str | None = "0008_export_retry_backoff"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "background_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(100), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="queued"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("worker_id", sa.String(200)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("error_class", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("kind", "idempotency_key", name="uq_background_job_kind_key"),
    )
    op.create_index(
        "ix_background_jobs_claimable",
        "background_jobs",
        ["status", "next_attempt_at", "created_at"],
    )
    op.create_table(
        "background_job_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("background_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.String(200), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error_class", sa.String(100)),
        sa.UniqueConstraint("job_id", "attempt_no", name="uq_background_attempt_job_no"),
    )
    op.create_index(
        "ix_background_attempt_job_status",
        "background_job_attempts",
        ["job_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_background_attempt_job_status", table_name="background_job_attempts")
    op.drop_table("background_job_attempts")
    op.drop_index("ix_background_jobs_claimable", table_name="background_jobs")
    op.drop_table("background_jobs")
