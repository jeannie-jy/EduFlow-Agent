"""add an explicit current project version pointer

Revision ID: 0019_project_current_version
Revises: 0018_audit_query_indexes
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0019_project_current_version"
down_revision: str | None = "0018_audit_query_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("current_version_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_projects_current_version",
        "projects",
        "project_versions",
        ["current_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_projects_current_version",
        "projects",
        ["current_version_id"],
    )
    op.execute(
        """
        UPDATE projects AS project
        SET current_version_id = latest.id
        FROM (
            SELECT DISTINCT ON (project_id) id, project_id
            FROM project_versions
            ORDER BY project_id, version DESC
        ) AS latest
        WHERE latest.project_id = project.id
        """
    )


def downgrade() -> None:
    op.drop_index("ix_projects_current_version", table_name="projects")
    op.drop_constraint(
        "fk_projects_current_version",
        "projects",
        type_="foreignkey",
    )
    op.drop_column("projects", "current_version_id")
