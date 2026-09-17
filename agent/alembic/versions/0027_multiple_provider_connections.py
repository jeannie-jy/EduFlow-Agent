"""support multiple provider connections with an explicit active selection"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0027_multi_provider_connections"
down_revision: str | None = "0026_one_active_cred_purpose"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("provider_credentials", sa.Column("name", sa.String(100)))
    op.add_column("provider_credentials", sa.Column("model", sa.String(200)))
    op.add_column("provider_credentials", sa.Column("base_url", sa.String(500)))
    op.execute(sa.text("""
        UPDATE provider_credentials
        SET
            name = CASE provider
                WHEN 'deepseek' THEN 'DeepSeek'
                WHEN 'dashscope' THEN '阿里云百炼'
                ELSE provider
            END,
            model = CASE
                WHEN provider = 'deepseek' THEN 'deepseek-chat'
                WHEN purpose = 'embedding' THEN 'text-embedding-v4'
                ELSE 'qwen-plus'
            END,
            base_url = CASE provider
                WHEN 'deepseek' THEN 'https://api.deepseek.com/v1'
                ELSE 'https://dashscope.aliyuncs.com/compatible-mode/v1'
            END
    """))
    op.alter_column("provider_credentials", "name", nullable=False)
    op.alter_column("provider_credentials", "model", nullable=False)
    op.alter_column("provider_credentials", "base_url", nullable=False)

    op.create_table(
        "active_provider_credentials",
        sa.Column(
            "user_id", sa.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True,
        ),
        sa.Column("purpose", sa.String(30), primary_key=True),
        sa.Column(
            "credential_id", sa.UUID(),
            sa.ForeignKey("provider_credentials.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint(
            "purpose IN ('generation', 'embedding')",
            name="ck_active_provider_credentials_purpose",
        ),
    )
    op.create_index(
        "ix_active_provider_credentials_credential",
        "active_provider_credentials",
        ["credential_id"],
    )
    op.execute(sa.text("""
        INSERT INTO active_provider_credentials (user_id, purpose, credential_id)
        SELECT user_id, purpose, id
        FROM (
            SELECT
                id, user_id, purpose,
                ROW_NUMBER() OVER (
                    PARTITION BY user_id, purpose
                    ORDER BY created_at DESC, version DESC, id DESC
                ) AS row_number
            FROM provider_credentials
            WHERE status = 'active'
        ) AS ranked
        WHERE row_number = 1
    """))

    op.drop_index(
        "ux_provider_credentials_one_active_per_purpose",
        table_name="provider_credentials",
    )
    op.drop_constraint(
        "ck_provider_credentials_provider", "provider_credentials", type_="check"
    )
    op.drop_constraint(
        "ck_provider_credentials_status", "provider_credentials", type_="check"
    )
    op.execute(sa.text("""
        UPDATE provider_credentials
        SET status = CASE WHEN validated_at IS NULL THEN 'unverified' ELSE 'valid' END
        WHERE status = 'active'
    """))
    op.create_check_constraint(
        "ck_provider_credentials_provider",
        "provider_credentials",
        "provider IN ('deepseek', 'dashscope', 'openai', 'ollama')",
    )
    op.create_check_constraint(
        "ck_provider_credentials_status",
        "provider_credentials",
        "status IN ('unverified', 'valid', 'invalid', 'revoked')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_provider_credentials_status", "provider_credentials", type_="check"
    )
    op.drop_constraint(
        "ck_provider_credentials_provider", "provider_credentials", type_="check"
    )
    op.execute(
        "UPDATE provider_credentials SET status = 'revoked' "
        "WHERE status IN ('unverified', 'valid')"
    )
    op.execute(sa.text("""
        UPDATE provider_credentials AS credentials
        SET status = 'active'
        FROM active_provider_credentials AS selected
        WHERE credentials.id = selected.credential_id
    """))
    # Newly-supported providers cannot be represented by the old schema.
    op.execute(
        "UPDATE provider_credentials SET provider = 'dashscope', status = 'revoked' "
        "WHERE provider NOT IN ('deepseek', 'dashscope')"
    )
    op.create_check_constraint(
        "ck_provider_credentials_provider",
        "provider_credentials",
        "provider IN ('deepseek', 'dashscope')",
    )
    op.create_check_constraint(
        "ck_provider_credentials_status",
        "provider_credentials",
        "status IN ('active', 'invalid', 'revoked')",
    )
    op.drop_index(
        "ix_active_provider_credentials_credential",
        table_name="active_provider_credentials",
    )
    op.drop_table("active_provider_credentials")
    op.drop_column("provider_credentials", "base_url")
    op.drop_column("provider_credentials", "model")
    op.drop_column("provider_credentials", "name")
    op.create_index(
        "ux_provider_credentials_one_active_per_purpose",
        "provider_credentials",
        ["user_id", "purpose"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
