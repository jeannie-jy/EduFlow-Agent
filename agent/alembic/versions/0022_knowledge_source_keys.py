"""add stable public identifiers for knowledge citations and evals

Revision ID: 0022_knowledge_source_keys
Revises: 0021_embedding_dimension
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0022_knowledge_source_keys"
down_revision: str | None = "0021_embedding_dimension"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE knowledge_base ADD COLUMN source_key VARCHAR(200)")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_knowledge_source_key "
        "ON knowledge_base (source_key) WHERE source_key IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_knowledge_source_key")
    op.execute("ALTER TABLE knowledge_base DROP COLUMN source_key")
