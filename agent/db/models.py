"""SQLAlchemy ORM 模型。

映射到 Alembic 管理的业务表结构。使用 async SQLAlchemy 2.0 风格。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """声明式基类。"""
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('student', 'teacher', 'admin')",
            name="ck_users_role",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    nickname: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="teacher", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_key: Mapped[Optional[str]] = mapped_column(String(1000))
    media_type: Mapped[str] = mapped_column(String(200), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="uploaded", nullable=False)
    parsed_result: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_actor_created", "actor_id", "created_at"),
        Index("ix_audit_events_resource", "resource_type", "resource_id"),
        Index("ix_audit_events_created", "created_at"),
        Index("ix_audit_events_action_created", "action", "created_at"),
        Index("ix_audit_events_request", "request_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(String(200))
    request_id: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ============================================================================
# Project
# ============================================================================


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (Index("ix_projects_current_version", "current_version_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    topic: Mapped[Optional[str]] = mapped_column(String(300))
    subject: Mapped[Optional[str]] = mapped_column(String(200))
    course: Mapped[Optional[str]] = mapped_column(String(300))
    audience: Mapped[str] = mapped_column(String(100), default="undergraduate_cs")
    difficulty: Mapped[str] = mapped_column(String(50), default="intermediate")
    owner_id: Mapped[Optional[str]] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(50), default="draft")
    dsl_snapshot: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    current_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "project_versions.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_projects_current_version",
        ),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # 关联
    frames: Mapped[list["Frame"]] = relationship(back_populates="project", lazy="raise", cascade="all, delete-orphan")
    parameters: Mapped[list["ParameterModel"]] = relationship(back_populates="project", lazy="raise", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Project id={self.id!s} title={self.title[:30]!r}>"


# ============================================================================
# Frame
# ============================================================================


class Frame(Base):
    __tablename__ = "frames"
    __table_args__ = (
        UniqueConstraint("project_id", "version", "frame_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    frame_id: Mapped[str] = mapped_column(String(50), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(500))
    learning_goal: Mapped[Optional[str]] = mapped_column(Text)
    narration: Mapped[Optional[str]] = mapped_column(Text)
    visual_objects: Mapped[Optional[list[dict]]] = mapped_column(JSONB)
    state_snapshot: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    animations: Mapped[Optional[list[dict]]] = mapped_column(JSONB)
    interaction_hooks: Mapped[Optional[list[dict]]] = mapped_column(JSONB)
    checks: Mapped[Optional[list[dict]]] = mapped_column(JSONB)
    quality_status: Mapped[str] = mapped_column(String(50), default="pending")
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # 关联
    project: Mapped[Project] = relationship(back_populates="frames")

    def __repr__(self) -> str:
        return f"<Frame project={self.project_id!s} {self.frame_id}>"


# ============================================================================
# Parameter
# ============================================================================


class ParameterModel(Base):
    __tablename__ = "parameters"
    __table_args__ = (
        UniqueConstraint("project_id", "key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    label: Mapped[Optional[str]] = mapped_column(String(500))
    param_type: Mapped[str] = mapped_column(String(50), nullable=False)
    default_value: Mapped[Optional[dict]] = mapped_column(JSONB)
    current_value: Mapped[Optional[dict]] = mapped_column(JSONB)
    constraints: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    visibility: Mapped[str] = mapped_column(String(50), default="student")
    recompute_scope: Mapped[str] = mapped_column(String(50), default="all_frames")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # 关联
    project: Mapped[Project] = relationship(back_populates="parameters")


# ============================================================================
# QualityReport
# ============================================================================


class QualityReportModel(Base):
    __tablename__ = "quality_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    scores: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    issues: Mapped[Optional[list[dict]]] = mapped_column(JSONB)
    suggestions: Mapped[Optional[list[dict]]] = mapped_column(JSONB)
    is_blocking: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ============================================================================
# ExportJob
# ============================================================================


class ExportJobModel(Base):
    __tablename__ = "export_jobs"
    __table_args__ = (
        Index(
            "ix_export_jobs_claimable",
            "status",
            "next_attempt_at",
            "lease_expires_at",
            "created_at",
        ),
        Index("ix_export_jobs_created", "created_at"),
        Index("ix_export_jobs_source_version", "source_version_id"),
        UniqueConstraint(
            "project_id",
            "target",
            "idempotency_key",
            name="uq_export_jobs_project_target_idempotency",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    source_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project_versions.id", ondelete="SET NULL"),
    )
    target: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="queued")
    config: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    progress_pct: Mapped[float] = mapped_column(Float, default=0.0)
    artifacts: Mapped[Optional[list[dict]]] = mapped_column(JSONB)
    error_log: Mapped[Optional[str]] = mapped_column(Text)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(200))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    worker_id: Mapped[Optional[str]] = mapped_column(String(200))
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    failure_retryable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class ExportJobAttempt(Base):
    """Immutable-numbered execution attempt for operational diagnosis."""

    __tablename__ = "export_job_attempts"
    __table_args__ = (
        UniqueConstraint("job_id", "attempt_no", name="uq_export_attempt_job_no"),
        Index("ix_export_attempt_job_status", "job_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("export_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    worker_id: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="rendering")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    heartbeat_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error_class: Mapped[Optional[str]] = mapped_column(String(100))


class BackgroundJob(Base):
    """Durable queue row for non-rendering asynchronous Agent work."""

    __tablename__ = "background_jobs"
    __table_args__ = (
        UniqueConstraint("kind", "idempotency_key", name="uq_background_job_kind_key"),
        Index("ix_background_jobs_claimable", "status", "next_attempt_at", "created_at"),
        Index("ix_background_jobs_owner_created", "owner_id", "created_at"),
        Index("ix_background_jobs_created", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE")
    )
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String(100), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="queued", nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    worker_id: Mapped[Optional[str]] = mapped_column(String(200))
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error_class: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class BackgroundJobAttempt(Base):
    __tablename__ = "background_job_attempts"
    __table_args__ = (
        UniqueConstraint("job_id", "attempt_no", name="uq_background_attempt_job_no"),
        Index("ix_background_attempt_job_status", "job_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("background_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    worker_id: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    heartbeat_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error_class: Mapped[Optional[str]] = mapped_column(String(100))


class WorkflowRun(Base):
    """Durable, sanitized trace for one workflow invocation."""

    __tablename__ = "workflow_runs"
    __table_args__ = (
        Index("ix_workflow_runs_project_started", "project_id", "started_at"),
        Index("ix_workflow_runs_status_started", "status", "started_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    request_id: Mapped[str] = mapped_column(String(100), nullable=False)
    thread_id: Mapped[str] = mapped_column(String(300), nullable=False)
    entrypoint: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="running")
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    error_class: Mapped[Optional[str]] = mapped_column(String(100))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class WorkflowNodeRun(Base):
    """Per-node trace containing metadata and usage, never prompt content."""

    __tablename__ = "workflow_node_runs"
    __table_args__ = (
        Index("ix_workflow_node_runs_workflow_started", "workflow_run_id", "started_at"),
        Index("ix_workflow_node_runs_started", "started_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False
    )
    graph_run_id: Mapped[Optional[str]] = mapped_column(String(100))
    node_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="running")
    model: Mapped[Optional[str]] = mapped_column(String(200))
    endpoint: Mapped[Optional[str]] = mapped_column(String(500))
    prompt_version: Mapped[Optional[str]] = mapped_column(String(100))
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    structured_parse_success: Mapped[Optional[bool]] = mapped_column(Boolean)
    error_class: Mapped[Optional[str]] = mapped_column(String(100))
    attributes: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql")
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[Optional[float]] = mapped_column(Float)


class ToolCallTrace(Base):
    """Sanitized audit record for one model-requested tool execution."""

    __tablename__ = "tool_call_traces"
    __table_args__ = (
        Index("ix_tool_call_traces_node_created", "workflow_node_run_id", "created_at"),
        Index("ix_tool_call_traces_created", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    workflow_node_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_node_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    tool_call_id: Mapped[str] = mapped_column(String(200), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tool_version: Mapped[Optional[str]] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    arguments_summary: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql")
    )
    result_summary: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql")
    )
    error_code: Mapped[Optional[str]] = mapped_column(String(100))
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SSEStream(Base):
    """Durable ownership/terminal state for one uniquely addressed SSE run."""

    __tablename__ = "sse_streams"
    __table_args__ = (
        Index("ix_sse_streams_project_created", "project_id", "created_at"),
        Index("ix_sse_streams_status_completed", "status", "completed_at"),
        Index("ix_sse_streams_created", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    last_event_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    producer_id: Mapped[Optional[str]] = mapped_column(String(100))
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class SSEEvent(Base):
    """Replayable SSE application event; written before network delivery."""

    __tablename__ = "sse_events"
    __table_args__ = (
        UniqueConstraint("stream_id", "event_id", name="uq_sse_event_stream_sequence"),
        Index("ix_sse_events_stream_event", "stream_id", "event_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    stream_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sse_streams.id", ondelete="CASCADE"), nullable=False
    )
    event_id: Mapped[int] = mapped_column(Integer, nullable=False)
    event_name: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ============================================================================
# Feedback (Phase 3)
# ============================================================================


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    frame_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("frames.id", ondelete="SET NULL")
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)   # rating / correction / suggestion
    content: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[Optional[int]] = mapped_column(Integer)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ============================================================================
# SourceMaterial (Phase 3)
# ============================================================================


class SourceMaterial(Base):
    __tablename__ = "source_materials"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)   # pdf / ppt / markdown / text / code
    filename: Mapped[Optional[str]] = mapped_column(String(500))
    content_text: Mapped[Optional[str]] = mapped_column(Text)
    parsed_result: Mapped[Optional[dict]] = mapped_column(JSONB)
    size_bytes: Mapped[Optional[int]] = mapped_column()
    storage_path: Mapped[Optional[str]] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ============================================================================
# ProjectVersion (Phase 3)
# ============================================================================


class ProjectVersion(Base):
    __tablename__ = "project_versions"
    __table_args__ = (
        UniqueConstraint("project_id", "version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    dsl_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    change_summary: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
