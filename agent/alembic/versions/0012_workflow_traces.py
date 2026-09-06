"""add durable workflow and node traces

Revision ID: 0012_workflow_traces
Revises: 0011_material_object_storage
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_workflow_traces"
down_revision: str | None = "0011_material_object_storage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workflow_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("request_id", sa.String(100), nullable=False),
        sa.Column("thread_id", sa.String(300), nullable=False),
        sa.Column("entrypoint", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="running"),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("error_class", sa.String(100)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_workflow_runs_project_started", "workflow_runs", ["project_id", "started_at"])
    op.create_index("ix_workflow_runs_status_started", "workflow_runs", ["status", "started_at"])
    op.create_table(
        "workflow_node_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workflow_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("graph_run_id", sa.String(100)),
        sa.Column("node_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="running"),
        sa.Column("model", sa.String(200)),
        sa.Column("endpoint", sa.String(500)),
        sa.Column("prompt_version", sa.String(100)),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("structured_parse_success", sa.Boolean()),
        sa.Column("error_class", sa.String(100)),
        sa.Column("attributes", postgresql.JSONB()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("duration_ms", sa.Float()),
    )
    op.create_index("ix_workflow_node_runs_workflow_started", "workflow_node_runs", ["workflow_run_id", "started_at"])


def downgrade() -> None:
    op.drop_index("ix_workflow_node_runs_workflow_started", table_name="workflow_node_runs")
    op.drop_table("workflow_node_runs")
    op.drop_index("ix_workflow_runs_status_started", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_project_started", table_name="workflow_runs")
    op.drop_table("workflow_runs")
