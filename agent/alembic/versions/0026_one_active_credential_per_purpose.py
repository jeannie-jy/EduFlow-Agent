"""allow only one active provider credential per user and purpose"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0026_one_active_cred_purpose"
down_revision: str | None = "0025_student_role_default"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Normalize installations created before the invariant existed. Keep the
    # newest credential for each purpose and retain older rows for audit history.
    op.execute(sa.text("""
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY user_id, purpose
                    ORDER BY created_at DESC, version DESC, id DESC
                ) AS row_number
            FROM provider_credentials
            WHERE status = 'active'
        )
        UPDATE provider_credentials AS credentials
        SET status = 'revoked'
        FROM ranked
        WHERE credentials.id = ranked.id
          AND ranked.row_number > 1
    """))
    op.create_index(
        "ux_provider_credentials_one_active_per_purpose",
        "provider_credentials",
        ["user_id", "purpose"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index(
        "ux_provider_credentials_one_active_per_purpose",
        table_name="provider_credentials",
    )
