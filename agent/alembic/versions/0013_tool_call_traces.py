"""add sanitized tool call traces

Revision ID: 0013_tool_call_traces
Revises: 0012_workflow_traces
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_tool_call_traces"
down_revision: str | None = "0012_workflow_traces"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tool_call_traces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workflow_node_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_node_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool_call_id", sa.String(200), nullable=False),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("tool_version", sa.String(50)),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("arguments_summary", postgresql.JSONB()),
        sa.Column("result_summary", postgresql.JSONB()),
        sa.Column("error_code", sa.String(100)),
        sa.Column("duration_ms", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_tool_call_traces_node_created", "tool_call_traces", ["workflow_node_run_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_tool_call_traces_node_created", table_name="tool_call_traces")
    op.drop_table("tool_call_traces")
