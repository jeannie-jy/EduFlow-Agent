"""baseline: 8 张 ORM 业务表 + knowledge_base

迁移说明
--------
- 由 db/models.py 的 SQLAlchemy 模型手工翻译（非 autogenerate，无需运行中的数据库）。
- knowledge_base 无 ORM 模型（services/knowledge_service.py 用原生 SQL 读写），
  列集以该服务的读写为准：concept/content/subject/difficulty/object_types/animation_types/embedding。
- 不建 long_term_memories / trajectories / tool_call_logs（旧架构遗留，全仓零引用；
  如未来恢复记忆功能请另开迁移）。
- 已存在的开发库无保留价值（旧 schema 与 ORM 零交集），请按 README 迁移小节
  执行 `docker compose down -v` 后重建，本迁移只针对全新数据库。

Revision ID: 0001
Revises:
Create Date: 2026-08-05
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── pgvector 扩展（knowledge_base.embedding 依赖）────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── projects ────────────────────────────────────────────────────
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("topic", sa.String(300), nullable=True),
        sa.Column("subject", sa.String(200), nullable=True),
        sa.Column("course", sa.String(300), nullable=True),
        sa.Column("audience", sa.String(100), nullable=False,
                  server_default="undergraduate_cs"),
        sa.Column("difficulty", sa.String(50), nullable=False,
                  server_default="intermediate"),
        sa.Column("owner_id", sa.String(200), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="draft"),
        sa.Column("dsl_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )

    # ── frames ──────────────────────────────────────────────────────
    op.create_table(
        "frames",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("frame_id", sa.String(50), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("learning_goal", sa.Text(), nullable=True),
        sa.Column("narration", sa.Text(), nullable=True),
        sa.Column("visual_objects", postgresql.JSONB(), nullable=True),
        sa.Column("state_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("animations", postgresql.JSONB(), nullable=True),
        sa.Column("interaction_hooks", postgresql.JSONB(), nullable=True),
        sa.Column("checks", postgresql.JSONB(), nullable=True),
        sa.Column("quality_status", sa.String(50), nullable=False,
                  server_default="pending"),
        sa.Column("is_locked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "version", "frame_id"),
    )

    # ── parameters ──────────────────────────────────────────────────
    op.create_table(
        "parameters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(200), nullable=False),
        sa.Column("label", sa.String(500), nullable=True),
        sa.Column("param_type", sa.String(50), nullable=False),
        sa.Column("default_value", postgresql.JSONB(), nullable=True),
        sa.Column("current_value", postgresql.JSONB(), nullable=True),
        sa.Column("constraints", postgresql.JSONB(), nullable=True),
        sa.Column("visibility", sa.String(50), nullable=False, server_default="student"),
        sa.Column("recompute_scope", sa.String(50), nullable=False,
                  server_default="all_frames"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "key"),
    )

    # ── quality_reports ─────────────────────────────────────────────
    op.create_table(
        "quality_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("scores", postgresql.JSONB(), nullable=True),
        sa.Column("issues", postgresql.JSONB(), nullable=True),
        sa.Column("suggestions", postgresql.JSONB(), nullable=True),
        sa.Column("is_blocking", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )

    # ── export_jobs ─────────────────────────────────────────────────
    op.create_table(
        "export_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="queued"),
        sa.Column("config", postgresql.JSONB(), nullable=True),
        sa.Column("progress_pct", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("artifacts", postgresql.JSONB(), nullable=True),
        sa.Column("error_log", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )

    # ── feedback ────────────────────────────────────────────────────
    op.create_table(
        "feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("frame_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["frame_id"], ["frames.id"], ondelete="SET NULL"),
    )

    # ── source_materials ────────────────────────────────────────────
    op.create_table(
        "source_materials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("filename", sa.String(500), nullable=True),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("parsed_result", postgresql.JSONB(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("storage_path", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )

    # ── project_versions ────────────────────────────────────────────
    op.create_table(
        "project_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("dsl_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("change_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "version"),
    )

    # ── knowledge_base（无 ORM 模型，列集对齐 services/knowledge_service.py）──
    op.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_base (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            concept VARCHAR(500) NOT NULL,
            content TEXT,
            subject VARCHAR(200),
            difficulty INT DEFAULT 3,
            object_types JSONB,
            animation_types JSONB,
            embedding VECTOR(1536),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_knowledge_embedding "
        "ON knowledge_base USING ivfflat (embedding vector_cosine_ops) "
        "WITH (lists = 100)"
    )


def downgrade() -> None:
    op.drop_table("knowledge_base")
    op.drop_table("project_versions")
    op.drop_table("source_materials")
    op.drop_table("feedback")
    op.drop_table("export_jobs")
    op.drop_table("quality_reports")
    op.drop_table("parameters")
    op.drop_table("frames")
    op.drop_table("projects")
    # 扩展保留（其他表可能依赖 vector 类型）
