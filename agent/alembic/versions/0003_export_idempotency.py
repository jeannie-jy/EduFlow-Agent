"""add export idempotency key

Revision ID: 0003_export_idempotency
Revises: 0002_export_job_leases
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_export_idempotency"
down_revision: str | None = "0002_export_job_leases"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "export_jobs",
        sa.Column("idempotency_key", sa.String(length=200), nullable=True),
    )
    op.create_unique_constraint(
        "uq_export_jobs_project_target_idempotency",
        "export_jobs",
        ["project_id", "target", "idempotency_key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_export_jobs_project_target_idempotency",
        "export_jobs",
        type_="unique",
    )
    op.drop_column("export_jobs", "idempotency_key")
