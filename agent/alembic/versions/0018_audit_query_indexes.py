"""add indexes for bounded audit queries

Revision ID: 0018_audit_query_indexes
Revises: 0017_export_source_version
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0018_audit_query_indexes"
down_revision: str | None = "0017_export_source_version"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_audit_events_created", "audit_events", ["created_at"])
    op.create_index(
        "ix_audit_events_action_created",
        "audit_events",
        ["action", "created_at"],
    )
    op.create_index("ix_audit_events_request", "audit_events", ["request_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_request", table_name="audit_events")
    op.drop_index("ix_audit_events_action_created", table_name="audit_events")
    op.drop_index("ix_audit_events_created", table_name="audit_events")
