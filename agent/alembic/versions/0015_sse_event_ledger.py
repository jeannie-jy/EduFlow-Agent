"""add durable SSE stream/event ledger

Revision ID: 0015_sse_event_ledger
Revises: 0014_material_parse_jobs
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015_sse_event_ledger"
down_revision: str | None = "0014_material_parse_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sse_streams",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("last_event_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("producer_id", sa.String(100)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_sse_streams_project_created", "sse_streams", ["project_id", "created_at"])
    op.create_index("ix_sse_streams_status_completed", "sse_streams", ["status", "completed_at"])
    op.create_table(
        "sse_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("stream_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sse_streams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("event_name", sa.String(50), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("stream_id", "event_id", name="uq_sse_event_stream_sequence"),
    )
    op.create_index("ix_sse_events_stream_event", "sse_events", ["stream_id", "event_id"])


def downgrade() -> None:
    op.drop_index("ix_sse_events_stream_event", table_name="sse_events")
    op.drop_table("sse_events")
    op.drop_index("ix_sse_streams_status_completed", table_name="sse_streams")
    op.drop_index("ix_sse_streams_project_created", table_name="sse_streams")
    op.drop_table("sse_streams")
