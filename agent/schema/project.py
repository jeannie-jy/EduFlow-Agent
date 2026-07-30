"""项目相关的 Pydantic 模型。

用于 API 层的数据校验和序列化，不与数据库直接耦合。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from .dsl import (
    AudienceEnum,
    DifficultyEnum,
    ExportStatus,
    ProjectStatus,
    QualityStatus,
    RenderScript,
)


# ============================================================================
# 项目
# ============================================================================


class ProjectCreateRequest(BaseModel):
    """创建项目请求。"""
    title: str = Field(..., min_length=1, max_length=500)
    input_type: str = Field(default="natural_language")
    input_content: str = ""
    audience: AudienceEnum = AudienceEnum.UNDERGRADUATE_CS
    difficulty: DifficultyEnum = DifficultyEnum.INTERMEDIATE
    constraints: dict[str, Any] = Field(default_factory=dict)


class ProjectCreateResponse(BaseModel):
    """创建项目响应。"""
    id: str
    title: str
    status: ProjectStatus = ProjectStatus.DRAFT
    created_at: datetime


class ProjectListItem(BaseModel):
    """项目列表项。"""
    id: str
    title: str
    topic: str | None = None
    difficulty: str = "intermediate"
    status: ProjectStatus = ProjectStatus.DRAFT
    frame_count: int = 0
    updated_at: datetime


class ProjectListResponse(BaseModel):
    """项目列表响应。"""
    items: list[ProjectListItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class ProjectDetailResponse(BaseModel):
    """项目详情响应。"""
    id: str
    title: str
    status: ProjectStatus = ProjectStatus.DRAFT
    audience: str = "undergraduate_cs"
    difficulty: str = "intermediate"
    teaching_plan: dict[str, Any] | None = None
    knowledge_graph: dict[str, Any] | None = None
    dsl: RenderScript | None = None
    quality_report: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


# ============================================================================
# 帧
# ============================================================================


class FrameResponse(BaseModel):
    """单帧响应。"""
    id: str
    frame_id: str
    order_index: int
    title: str = ""
    narration: str = ""
    visual_objects: list[dict[str, Any]] = Field(default_factory=list)
    state_snapshot: dict[str, Any] = Field(default_factory=dict)
    animations: list[dict[str, Any]] = Field(default_factory=list)
    interaction_hooks: list[dict[str, Any]] = Field(default_factory=list)
    quality_status: QualityStatus = QualityStatus.PENDING
    is_locked: bool = False


class FrameListResponse(BaseModel):
    """帧列表响应。"""
    frames: list[FrameResponse] = Field(default_factory=list)
    version: int = 1


class FrameUpdateRequest(BaseModel):
    """编辑单帧请求。"""
    title: str | None = None
    narration: str | None = None
    visual_objects: list[dict[str, Any]] | None = None
    state_snapshot: dict[str, Any] | None = None
    animations: list[dict[str, Any]] | None = None


class FrameLockRequest(BaseModel):
    """锁定/解锁帧请求。"""
    is_locked: bool


# ============================================================================
# 参数
# ============================================================================


class ParameterResponse(BaseModel):
    """参数响应。"""
    id: str
    key: str
    label: str
    param_type: str
    default_value: Any = None
    current_value: Any = None
    constraints: dict[str, Any] = Field(default_factory=dict)
    recompute_scope: str = "all_frames"


class ParameterListResponse(BaseModel):
    """参数列表响应。"""
    parameters: list[ParameterResponse] = Field(default_factory=list)


class RecomputeRequest(BaseModel):
    """参数变更重算请求。"""
    changed_params: dict[str, Any] = Field(..., description="key → new_value 映射")


# ============================================================================
# 生成流程
# ============================================================================


class GenerateRequest(BaseModel):
    """启动生成请求。"""
    action: str = "full"     # full / plan_only / modules


class GenerateResponse(BaseModel):
    """启动生成响应。"""
    stream_url: str


class ModuleSelectRequest(BaseModel):
    """模块选择请求。"""
    modules: list[str] = Field(
        ...,
        min_length=1,
        description="要生成的模块 ID 列表，如 ['mindmap', 'cards', 'frames']",
    )


class ModuleInfo(BaseModel):
    """模块元信息（供前端模块选择器渲染）。"""
    module_id: str
    display_name: str
    description: str = ""
    icon: str = "box"
    category: str = "visual"
    priority: int = 5
    estimated_seconds: int = 30


class ModuleListResponse(BaseModel):
    """可用模块列表响应。"""
    modules: list[ModuleInfo] = Field(default_factory=list)


class RegenerateRequest(BaseModel):
    """局部重生成请求。"""
    scope: dict[str, Any] = Field(...)


class RejectPlanRequest(BaseModel):
    """拒绝教学计划请求（含修改意见）。"""
    feedback: str = Field(default="", description="用户修改意见")


class ApprovePlanResponse(BaseModel):
    """批准教学计划响应。"""
    stream_url: str
    available_modules: list[ModuleInfo] = Field(default_factory=list)


# ============================================================================
# 导出
# ============================================================================


class ExportManimRequest(BaseModel):
    """Manim 导出请求。"""
    quality: Literal["l", "m", "h", "k"] = "h"
    format: str = "mp4"
    fps: int = Field(default=30, ge=1, le=120, description="视频帧率")
    include_subtitles: bool = True
    include_tts: bool = False


class CreateVersionRequest(BaseModel):
    """保存版本请求。"""
    change_summary: str = ""


class ExportCreateResponse(BaseModel):
    """创建导出任务响应。"""
    job_id: str
    status: str = "queued"


class ExportArtifact(BaseModel):
    """导出产物。"""
    type: str                      # mp4 / manim_source / subtitle
    url: str
    size_bytes: int = 0


class ExportJobResponse(BaseModel):
    """导出任务状态响应。"""
    job_id: str
    status: ExportStatus = ExportStatus.QUEUED
    progress_pct: float = 0.0
    artifacts: list[ExportArtifact] | None = None
    error_log: str | None = None
    duration_ms: int | None = None
    total_frames: int | None = None


# ============================================================================
# 知识库
# ============================================================================


class KnowledgeSearchRequest(BaseModel):
    """语义检索请求。"""
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)


class KnowledgeSearchResult(BaseModel):
    """检索结果项。"""
    id: str
    concept: str
    content: str = ""
    subject: str | None = None
    difficulty: int = 3
    similarity: float = 0.0


class KnowledgeSearchResponse(BaseModel):
    """语义检索响应。"""
    results: list[KnowledgeSearchResult] = Field(default_factory=list)


class KnowledgeTemplate(BaseModel):
    """知识点模板。"""
    id: str
    concept: str
    subject: str | None = None
    difficulty: int = 3
    object_types: list[str] = Field(default_factory=list)


class KnowledgeTemplateListResponse(BaseModel):
    """模板列表响应。"""
    templates: list[KnowledgeTemplate] = Field(default_factory=list)


# ============================================================================
# 素材
# ============================================================================


class MaterialUploadResponse(BaseModel):
    """上传素材响应。"""
    id: str
    filename: str
    type: str
    size_bytes: int


class MaterialParseResponse(BaseModel):
    """解析素材响应。"""
    id: str
    status: str
    parsed_result: dict[str, Any] | None = None


# ============================================================================
# 反馈
# ============================================================================


class FeedbackRequest(BaseModel):
    """提交反馈请求。"""
    frame_id: str | None = None
    type: str = "correction"       # rating / correction / suggestion
    content: str = Field(..., min_length=1)
    rating: int | None = Field(default=None, ge=1, le=5)


class FeedbackResponse(BaseModel):
    """提交反馈响应。"""
    id: str


# ============================================================================
# 通用
# ============================================================================


class ErrorResponse(BaseModel):
    """错误响应。"""
    error: dict[str, Any]
