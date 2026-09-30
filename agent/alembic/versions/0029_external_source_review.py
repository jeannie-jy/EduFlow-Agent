"""Admin allowlist and non-public external sync candidates.

Revision ID: 0029_external_source_review
Revises: 0028_knowledge_library
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0029_external_source_review"
down_revision: str | None = "0028_knowledge_library"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "external_source_allowlist",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("url", sa.Text(), nullable=False, unique=True),
        sa.Column("institution", sa.String(300), nullable=False),
        sa.Column("license_note", sa.Text(), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("knowledge_sources.id", ondelete="SET NULL"), unique=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("next_sync_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_checked_at", sa.DateTime(timezone=True)),
        sa.Column("last_remote_checksum", sa.String(64)),
        sa.Column("last_error", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_external_source_due", "external_source_allowlist", ["active", "next_sync_at"]
    )
    op.create_table(
        "external_sync_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("allowlist_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("external_source_allowlist.id", ondelete="CASCADE"), nullable=False),
        sa.Column("remote_checksum", sa.String(64), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("title", sa.String(500)),
        sa.Column("section", sa.String(500)),
        sa.Column("document_version", sa.String(100)),
        sa.Column("summary", sa.Text()),
        sa.Column("author", sa.String(300)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("license", sa.String(300)),
        sa.Column("etag", sa.String(500)),
        sa.Column("last_modified", sa.String(200)),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_external_candidate_status"),
        sa.UniqueConstraint("allowlist_id", "remote_checksum", name="uq_external_candidate_remote_checksum"),
    )
    op.create_index("ix_external_candidate_status", "external_sync_candidates", ["status", "created_at"])


def downgrade() -> None:
    op.drop_table("external_sync_candidates")
    op.drop_table("external_source_allowlist")
