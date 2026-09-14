"""make student the database default role for new accounts

Revision ID: 0025_student_role_default
Revises: 0024_user_mfa
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025_student_role_default"
down_revision: str | None = "0024_user_mfa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Do not rewrite existing roles; only new rows use the safer public default.
    op.alter_column(
        "users",
        "role",
        existing_type=sa.String(length=50),
        server_default=sa.text("'student'"),
    )


def downgrade() -> None:
    op.alter_column(
        "users",
        "role",
        existing_type=sa.String(length=50),
        server_default=sa.text("'teacher'"),
    )
