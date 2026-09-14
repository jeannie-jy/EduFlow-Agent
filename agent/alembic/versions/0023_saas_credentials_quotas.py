"""add encrypted BYOK credentials and user quota ledger

Revision ID: 0023_saas_credentials_quotas
Revises: 0022_knowledge_source_keys
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023_saas_credentials_quotas"
down_revision: str | None = "0022_knowledge_source_keys"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True)))
    # Existing authenticated installations are grandfathered in; only new public
    # registrations enter the verification flow.
    op.execute("UPDATE users SET email_verified_at = CURRENT_TIMESTAMP WHERE email_verified_at IS NULL")
    op.create_table(
        "provider_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("purpose", sa.String(30), nullable=False),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("encrypted_data_key", sa.Text(), nullable=False),
        sa.Column("nonce", sa.String(100), nullable=False),
        sa.Column("key_fingerprint", sa.String(64), nullable=False),
        sa.Column("key_last_four", sa.String(4), nullable=False),
        sa.Column("kms_key_version", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("validated_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("provider IN ('deepseek', 'dashscope')", name="ck_provider_credentials_provider"),
        sa.CheckConstraint("purpose IN ('generation', 'embedding')", name="ck_provider_credentials_purpose"),
        sa.CheckConstraint("status IN ('active', 'invalid', 'revoked')", name="ck_provider_credentials_status"),
        sa.UniqueConstraint("user_id", "provider", "purpose", "version"),
    )
    op.create_index("ix_provider_credentials_user_status", "provider_credentials", ["user_id", "status"])
    op.create_table(
        "usage_buckets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resource", sa.String(50), nullable=False),
        sa.Column("period", sa.String(10), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "resource", "period", "period_start"),
    )
    op.create_index("ix_usage_buckets_user_period", "usage_buckets", ["user_id", "period_start"])
    op.create_table(
        "usage_ledger",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resource", sa.String(50), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("details", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "resource", "idempotency_key"),
    )
    op.create_index("ix_usage_ledger_user_created", "usage_ledger", ["user_id", "created_at"])
    op.create_table(
        "user_quota_policies",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("limits", postgresql.JSONB()),
        sa.Column("is_suspended", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "user_consents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("policy", sa.String(50), nullable=False),
        sa.Column("policy_version", sa.String(50), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "policy", "policy_version"),
    )
    op.create_table(
        "account_deletion_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("execute_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "auth_one_time_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purpose", sa.String(30), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("purpose IN ('verify_email', 'reset_password')", name="ck_auth_one_time_tokens_purpose"),
    )
    op.create_index("ix_auth_one_time_tokens_user_purpose", "auth_one_time_tokens", ["user_id", "purpose"])
    op.create_index("ix_auth_one_time_tokens_expires", "auth_one_time_tokens", ["expires_at"])


def downgrade() -> None:
    op.drop_table("auth_one_time_tokens")
    op.drop_table("account_deletion_requests")
    op.drop_table("user_consents")
    op.drop_table("user_quota_policies")
    op.drop_table("usage_ledger")
    op.drop_table("usage_buckets")
    op.drop_table("provider_credentials")
    op.drop_column("users", "email_verified_at")
