"""Versioned knowledge sources and scoped teaching material library.

Revision ID: 0028_knowledge_library
Revises: 0027_multi_provider_connections
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0028_knowledge_library"
down_revision: str | None = "0027_multi_provider_connections"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.add_column(
        "materials", sa.Column("is_library", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.alter_column("materials", "expires_at", existing_type=sa.DateTime(timezone=True), nullable=True)

    op.create_table(
        "knowledge_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_key", sa.String(240), nullable=False, unique=True),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("material_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("materials.id", ondelete="CASCADE"), unique=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("subject", sa.String(100)),
        sa.Column("difficulty", sa.Integer()),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("source_url", sa.Text()),
        sa.Column("source_type", sa.String(50)),
        sa.Column("author", sa.String(300)),
        sa.Column("license", sa.String(300)),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("scope IN ('builtin', 'teacher', 'external')", name="ck_knowledge_scope"),
        sa.CheckConstraint("status IN ('draft', 'published', 'retired')", name="ck_knowledge_status"),
        sa.CheckConstraint("scope <> 'teacher' OR owner_id IS NOT NULL", name="ck_teacher_knowledge_owner"),
    )
    op.create_index("ix_knowledge_sources_owner_scope", "knowledge_sources", ["owner_id", "scope"])
    op.create_table(
        "knowledge_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.String(100), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("embedding_model", sa.String(200)),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("review_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("indexed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("source_id", "version", name="uq_knowledge_source_version"),
    )
    op.create_index(
        "uq_knowledge_current_version", "knowledge_versions", ["source_id"], unique=True,
        postgresql_where=sa.text("is_current"),
    )
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("section", sa.String(500)),
        sa.Column("locator", sa.String(100)),
        sa.Column("content", sa.Text(), nullable=False),
        sa.UniqueConstraint("version_id", "ordinal", name="uq_knowledge_chunk_ordinal"),
    )
    op.execute("ALTER TABLE knowledge_chunks ADD COLUMN embedding vector(1024)")
    op.execute(
        "CREATE INDEX ix_knowledge_chunks_embedding ON knowledge_chunks "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )
    op.execute(
        "CREATE INDEX ix_knowledge_chunks_content_trgm ON knowledge_chunks "
        "USING gin (content gin_trgm_ops)"
    )
    op.create_index("ix_knowledge_chunks_version", "knowledge_chunks", ["version_id"])
    op.create_table(
        "project_knowledge_sources",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_sources.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("project_knowledge_sources")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_versions")
    op.drop_table("knowledge_sources")
    op.execute("UPDATE materials SET expires_at = now() WHERE expires_at IS NULL")
    op.alter_column("materials", "expires_at", existing_type=sa.DateTime(timezone=True), nullable=False)
    op.drop_column("materials", "is_library")
