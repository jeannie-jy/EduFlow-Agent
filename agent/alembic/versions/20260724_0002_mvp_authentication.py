"""mvp authentication

Revision ID: 20260724_0002
Revises: 20260724_0001
Create Date: 2026-07-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260724_0002"
down_revision: Union[str, Sequence[str], None] = "20260724_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("email_normalized", sa.String(length=320), nullable=False),
        sa.Column("nickname", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email_normalized", name="uq_users_email_normalized"),
    )
    op.create_table(
        "auth_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["replaced_by_id"],
            ["auth_sessions.id"],
            name="fk_auth_sessions_replaced_by_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_auth_sessions_user_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "refresh_token_hash", name="uq_auth_sessions_refresh_token_hash"
        ),
    )

    # This migration creates an empty users table, so no legacy owner ID can
    # reference a valid user yet. Clear every legacy value before adding the FK.
    op.execute("UPDATE projects SET owner_id = NULL WHERE owner_id IS NOT NULL")
    op.alter_column(
        "projects",
        "owner_id",
        existing_type=sa.String(length=200),
        type_=postgresql.UUID(as_uuid=True),
        nullable=True,
        postgresql_using="owner_id::uuid",
    )
    op.create_foreign_key(
        "fk_projects_owner_id_users",
        "projects",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_projects_owner_id", "projects", ["owner_id"])

    op.add_column(
        "source_materials",
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_source_materials_owner_id_users",
        "source_materials",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_source_materials_owner_id", "source_materials", ["owner_id"])
    op.alter_column(
        "source_materials",
        "project_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )

    op.create_index(
        "idx_auth_sessions_user_active", "auth_sessions", ["user_id", "revoked_at"]
    )
    op.create_index("idx_auth_sessions_family", "auth_sessions", ["family_id"])


def downgrade() -> None:
    op.drop_index("idx_auth_sessions_family", table_name="auth_sessions")
    op.drop_index("idx_auth_sessions_user_active", table_name="auth_sessions")

    # The baseline schema cannot represent owner-only materials. Removing them
    # is the explicit, data-destructive downgrade policy before NOT NULL returns.
    op.execute("DELETE FROM source_materials WHERE project_id IS NULL")
    op.alter_column(
        "source_materials",
        "project_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    op.drop_index("ix_source_materials_owner_id", table_name="source_materials")
    op.drop_constraint(
        "fk_source_materials_owner_id_users", "source_materials", type_="foreignkey"
    )
    op.drop_column("source_materials", "owner_id")

    op.drop_index("ix_projects_owner_id", table_name="projects")
    op.drop_constraint("fk_projects_owner_id_users", "projects", type_="foreignkey")
    op.alter_column(
        "projects",
        "owner_id",
        existing_type=postgresql.UUID(as_uuid=True),
        type_=sa.String(length=200),
        nullable=True,
        postgresql_using="owner_id::text",
    )

    op.drop_table("auth_sessions")
    op.drop_table("users")
