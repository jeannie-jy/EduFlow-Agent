"""add indexes for bounded operational metric windows

Revision ID: 0016_observability_indexes
Revises: 0015_sse_event_ledger
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0016_observability_indexes"
down_revision: str | None = "0015_sse_event_ledger"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_export_jobs_created", "export_jobs", ["created_at"])
    op.create_index("ix_background_jobs_created", "background_jobs", ["created_at"])
    op.create_index("ix_workflow_node_runs_started", "workflow_node_runs", ["started_at"])
    op.create_index("ix_tool_call_traces_created", "tool_call_traces", ["created_at"])
    op.create_index("ix_sse_streams_created", "sse_streams", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_sse_streams_created", table_name="sse_streams")
    op.drop_index("ix_tool_call_traces_created", table_name="tool_call_traces")
    op.drop_index("ix_workflow_node_runs_started", table_name="workflow_node_runs")
    op.drop_index("ix_background_jobs_created", table_name="background_jobs")
    op.drop_index("ix_export_jobs_created", table_name="export_jobs")
