"""compact duplicated frame module outputs into immutable artifact references

Revision ID: 0020_compact_frame_artifact_refs
Revises: 0019_project_current_version
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0020_compact_frame_artifact_refs"
down_revision: str | None = "0019_project_current_version"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Each immutable version owns its top-level frames payload. Remove the
    # duplicate nested array and retain a resolvable reference to that version.
    op.execute(
        """
        UPDATE project_versions
        SET dsl_snapshot = jsonb_set(
            dsl_snapshot #- '{module_outputs,frames,frames}',
            '{module_outputs,frames,artifact_ref}',
            jsonb_build_object(
                'type', 'project_version_frames',
                'version_id', id::text
            ),
            true
        )
        WHERE jsonb_typeof(dsl_snapshot #> '{frames}') = 'array'
          AND jsonb_typeof(
              dsl_snapshot #> '{module_outputs,frames,frames}'
          ) = 'array'
        """
    )
    # Active snapshots point at the explicit current version introduced in
    # 0019. Dirty working copies have no pointer and are deliberately skipped.
    op.execute(
        """
        UPDATE projects
        SET dsl_snapshot = jsonb_set(
            dsl_snapshot #- '{module_outputs,frames,frames}',
            '{module_outputs,frames,artifact_ref}',
            jsonb_build_object(
                'type', 'project_version_frames',
                'version_id', current_version_id::text
            ),
            true
        )
        WHERE current_version_id IS NOT NULL
          AND jsonb_typeof(dsl_snapshot #> '{frames}') = 'array'
          AND jsonb_typeof(
              dsl_snapshot #> '{module_outputs,frames,frames}'
          ) = 'array'
        """
    )


def downgrade() -> None:
    # Top-level frames remains self-contained, so the legacy nested copy can be
    # reconstructed without data loss.
    op.execute(
        """
        UPDATE project_versions
        SET dsl_snapshot = jsonb_set(
            dsl_snapshot #- '{module_outputs,frames,artifact_ref}',
            '{module_outputs,frames,frames}',
            dsl_snapshot -> 'frames',
            true
        )
        WHERE jsonb_typeof(dsl_snapshot #> '{frames}') = 'array'
          AND dsl_snapshot #>> '{module_outputs,frames,artifact_ref,type}'
              = 'project_version_frames'
        """
    )
    op.execute(
        """
        UPDATE projects
        SET dsl_snapshot = jsonb_set(
            dsl_snapshot #- '{module_outputs,frames,artifact_ref}',
            '{module_outputs,frames,frames}',
            dsl_snapshot -> 'frames',
            true
        )
        WHERE jsonb_typeof(dsl_snapshot #> '{frames}') = 'array'
          AND dsl_snapshot #>> '{module_outputs,frames,artifact_ref,type}'
              = 'project_version_frames'
        """
    )
