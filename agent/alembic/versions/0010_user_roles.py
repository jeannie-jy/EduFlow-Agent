"""add user roles

Revision ID: 0010_user_roles
Revises: 0009_background_jobs
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_user_roles"
down_revision: str | None = "0009_background_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(50), nullable=False, server_default="teacher"),
    )
    op.create_check_constraint(
        "ck_users_role",
        "users",
        "role IN ('student', 'teacher', 'admin')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_column("users", "role")
