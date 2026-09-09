"""add owned material metadata and retention

Revision ID: 0005_material_ownership
Revises: 0004_auth_sessions
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_material_ownership"
down_revision: str | None = "0004_auth_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "materials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("original_filename", sa.String(length=500), nullable=False),
        sa.Column("stored_filename", sa.String(length=500), nullable=False),
        sa.Column("media_type", sa.String(length=200), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="uploaded"),
        sa.Column("parsed_result", postgresql.JSONB(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_materials_owner_created", "materials", ["owner_id", "created_at"])
    op.create_index("ix_materials_expires_at", "materials", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_materials_expires_at", table_name="materials")
    op.drop_index("ix_materials_owner_created", table_name="materials")
    op.drop_table("materials")
