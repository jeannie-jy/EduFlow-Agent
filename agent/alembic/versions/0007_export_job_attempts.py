"""add export job attempt history

Revision ID: 0007_export_job_attempts
Revises: 0006_audit_events
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_export_job_attempts"
down_revision: str | None = "0006_audit_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "export_job_attempts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.func.gen_random_uuid(),
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("export_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error_class", sa.String(length=100)),
        sa.UniqueConstraint("job_id", "attempt_no", name="uq_export_attempt_job_no"),
    )
    op.create_index(
        "ix_export_attempt_job_status",
        "export_job_attempts",
        ["job_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_export_attempt_job_status", table_name="export_job_attempts")
    op.drop_table("export_job_attempts")
