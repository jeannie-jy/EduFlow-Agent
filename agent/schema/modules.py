"""模块生成相关的 Pydantic 模型。

各模块产出格式等 API 层数据模型。
注意：模块选择请求/模块信息/模块列表响应等模型定义在 schema/project.py（API 唯一真源），
本文件只保留各模块的产出格式定义。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ============================================================================
# 各模块产出格式（Phase B+ 逐步启用）
# ============================================================================


class MindmapOutput(BaseModel):
    """思维导图模块产出。"""
    root: dict[str, Any] = Field(
        default_factory=lambda: {"name": "", "children": []},
        description="思维导图根节点: {name, children: [{name, children, ...}]}",
    )


class CardOutput(BaseModel):
    """知识卡片产出（单张）。"""
    id: str
    title: str
    definition: str = ""
    intuition: str = ""
    pitfalls: list[str] = Field(default_factory=list)
    formula: str | None = None
    pseudocode: str | None = None
    related_frame_ids: list[str] = Field(default_factory=list)
    category: str = "core_concept"
    difficulty: int = 1


class CardsOutput(BaseModel):
    """知识卡片模块产出。"""
    cards: list[CardOutput] = Field(default_factory=list)


class QuizQuestion(BaseModel):
    """练习题。"""
    id: str
    type: str = "multiple_choice"  # multiple_choice / fill_blank / true_false / short_answer
    question: str
    options: list[dict[str, Any]] | None = None  # [{id, text, is_correct}]
    correct_answer: str | None = None
    explanation: str = ""
    related_concept: str = ""
    difficulty: int = 1


class QuizOutput(BaseModel):
    """小练习模块产出。"""
    questions: list[QuizQuestion] = Field(default_factory=list)


class ComparisonOutput(BaseModel):
    """算法对比模块产出。"""
    topic: str = ""
    algorithms: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    comparison_table: list[dict[str, Any]] = Field(default_factory=list)
    scenario_analysis: str = ""


class MisconceptionItem(BaseModel):
    """常见误区项。"""
    id: str
    misconception: str  # 错误理解
    correction: str     # 正确理解
    example: str = ""   # 反例说明
    related_concept: str = ""


class MisconceptionOutput(BaseModel):
    """常见误区模块产出。"""
    items: list[MisconceptionItem] = Field(default_factory=list)


class PathwayOutput(BaseModel):
    """学习路径模块产出。"""
    current_topic: str = ""
    prerequisites: list[dict[str, Any]] = Field(default_factory=list)
    extensions: list[dict[str, Any]] = Field(default_factory=list)
    related_topics: list[dict[str, Any]] = Field(default_factory=list)


class SandboxOutput(BaseModel):
    """代码沙箱模块产出。"""
    language: str = "python"
    starter_code: str = ""
    test_cases: list[dict[str, Any]] = Field(default_factory=list)
    editable_params: list[dict[str, Any]] = Field(default_factory=list)


class PptxOutput(BaseModel):
    """PPTX 讲义模块产出。"""
    slides: list[dict[str, Any]] = Field(default_factory=list)
    total_slides: int = 0


class TtsOutput(BaseModel):
    """TTS 语音解说模块产出。"""
    audio_url: str = ""
    duration_seconds: float = 0.0
    subtitles: list[dict[str, Any]] = Field(default_factory=list)


class VideoOutput(BaseModel):
    """Manim 视频模块产出。"""
    job_id: str = ""
    status: str = "queued"
    config: dict[str, Any] = Field(default_factory=dict)


class ExportOutput(BaseModel):
    """导出总产出容器。"""
    job_id: str = ""
    config: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# 模块产出聚合容器（未使用）
# ============================================================================


class ModuleOutputs(BaseModel):
    """所有模块产出的聚合容器。

    ⚠️ 未使用：实际产出以各 generator 的裸 dict 存储于
    project.dsl_snapshot['module_outputs']（module_dispatcher 落库），
    本模型字段与实际产出形状不符（如 cards 实际是 {"cards": [...]} 而非 list），
    仅保留作为类型参考，勿用于校验。
    """
    mindmap: dict[str, Any] | None = None
    cards: list[dict[str, Any]] | None = None
    quiz: list[dict[str, Any]] | None = None
    frames: dict[str, Any] | None = None
    video: dict[str, Any] | None = None
    comparison: dict[str, Any] | None = None
    misconception: list[dict[str, Any]] | None = None
    pathway: dict[str, Any] | None = None
    sandbox: dict[str, Any] | None = None
    pptx: dict[str, Any] | None = None
    tts: dict[str, Any] | None = None
