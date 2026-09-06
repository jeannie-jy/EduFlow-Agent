"""store uploaded materials in ArtifactStore

Revision ID: 0011_material_object_storage
Revises: 0010_user_roles
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_material_object_storage"
down_revision: str | None = "0010_user_roles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "materials",
        sa.Column("storage_key", sa.String(length=1000), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("materials", "storage_key")
