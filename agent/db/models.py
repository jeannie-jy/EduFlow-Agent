"""SQLAlchemy ORM 模型。

映射到 init.sql 中定义的表结构。使用 async SQLAlchemy 2.0 风格。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """声明式基类。"""
    pass


# ============================================================================
# Project
# ============================================================================


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    topic: Mapped[str | None] = mapped_column(String(300))
    subject: Mapped[str | None] = mapped_column(String(200))
    course: Mapped[str | None] = mapped_column(String(300))
    audience: Mapped[str] = mapped_column(String(100), default="undergraduate_cs")
    difficulty: Mapped[str] = mapped_column(String(50), default="intermediate")
    owner_id: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(50), default="draft")
    dsl_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # 关联
    frames: Mapped[list["Frame"]] = relationship(back_populates="project", lazy="raise")
    parameters: Mapped[list["ParameterModel"]] = relationship(back_populates="project", lazy="raise")

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
    title: Mapped[str | None] = mapped_column(String(500))
    learning_goal: Mapped[str | None] = mapped_column(Text)
    narration: Mapped[str | None] = mapped_column(Text)
    visual_objects: Mapped[list[dict] | None] = mapped_column(JSONB)
    state_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    animations: Mapped[list[dict] | None] = mapped_column(JSONB)
    interaction_hooks: Mapped[list[dict] | None] = mapped_column(JSONB)
    checks: Mapped[list[dict] | None] = mapped_column(JSONB)
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
    label: Mapped[str | None] = mapped_column(String(500))
    param_type: Mapped[str] = mapped_column(String(50), nullable=False)
    default_value: Mapped[dict | None] = mapped_column(JSONB)
    current_value: Mapped[dict | None] = mapped_column(JSONB)
    constraints: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
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
    scores: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    issues: Mapped[list[dict] | None] = mapped_column(JSONB)
    suggestions: Mapped[list[dict] | None] = mapped_column(JSONB)
    is_blocking: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ============================================================================
# ExportJob
# ============================================================================


class ExportJobModel(Base):
    __tablename__ = "export_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    target: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="queued")
    config: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    progress_pct: Mapped[float] = mapped_column(Float, default=0.0)
    artifacts: Mapped[list[dict] | None] = mapped_column(JSONB)
    error_log: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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
    frame_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("frames.id", ondelete="SET NULL")
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)   # rating / correction / suggestion
    content: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[int | None] = mapped_column(Integer)
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
    filename: Mapped[str | None] = mapped_column(String(500))
    content_text: Mapped[str | None] = mapped_column(Text)
    parsed_result: Mapped[dict | None] = mapped_column(JSONB)
    size_bytes: Mapped[int | None] = mapped_column()
    storage_path: Mapped[str | None] = mapped_column(String(1000))
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
    change_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
