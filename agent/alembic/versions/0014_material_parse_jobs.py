"""allow owner-scoped material parse jobs

Revision ID: 0014_material_parse_jobs
Revises: 0013_tool_call_traces
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_material_parse_jobs"
down_revision: str | None = "0013_tool_call_traces"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("background_jobs", "project_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.add_column("background_jobs", sa.Column("owner_id", postgresql.UUID(as_uuid=True)))
    op.create_foreign_key(
        "fk_background_jobs_owner_id_users",
        "background_jobs", "users", ["owner_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index("ix_background_jobs_owner_created", "background_jobs", ["owner_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_background_jobs_owner_created", table_name="background_jobs")
    op.drop_constraint("fk_background_jobs_owner_id_users", "background_jobs", type_="foreignkey")
    op.drop_column("background_jobs", "owner_id")
    op.execute("DELETE FROM background_jobs WHERE project_id IS NULL")
    op.alter_column("background_jobs", "project_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
