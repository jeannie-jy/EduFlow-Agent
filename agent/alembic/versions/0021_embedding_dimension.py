"""align knowledge embeddings with the configured provider dimension

Revision ID: 0021_embedding_dimension
Revises: 0020_compact_frame_artifact_refs
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0021_embedding_dimension"
down_revision: str | None = "0020_compact_frame_artifact_refs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # pgvector cannot cast an existing 1536-dimensional vector to 1024
    # without changing its meaning. Preserve the knowledge rows and metadata,
    # clear only the stale vectors, then let seed_embeddings regenerate them.
    op.execute("DROP INDEX IF EXISTS idx_knowledge_embedding")
    op.execute(
        "ALTER TABLE knowledge_base "
        "ADD COLUMN embedding_v2 vector(1024)"
    )
    op.execute("ALTER TABLE knowledge_base DROP COLUMN embedding")
    op.execute(
        "ALTER TABLE knowledge_base "
        "RENAME COLUMN embedding_v2 TO embedding"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_knowledge_embedding "
        "ON knowledge_base USING ivfflat (embedding vector_cosine_ops) "
        "WITH (lists = 100)"
    )


def downgrade() -> None:
    # The old vectors are not recoverable after a dimension change; callers
    # must re-run the seed script after downgrading as well.
    op.execute("DROP INDEX IF EXISTS idx_knowledge_embedding")
    op.execute(
        "ALTER TABLE knowledge_base "
        "ADD COLUMN embedding_v2 vector(1536)"
    )
    op.execute("ALTER TABLE knowledge_base DROP COLUMN embedding")
    op.execute(
        "ALTER TABLE knowledge_base "
        "RENAME COLUMN embedding_v2 TO embedding"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_knowledge_embedding "
        "ON knowledge_base USING ivfflat (embedding vector_cosine_ops) "
        "WITH (lists = 100)"
    )
