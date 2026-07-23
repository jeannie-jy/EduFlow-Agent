"""EduFlow-Agent DSL Schema — Pydantic 模型。

教学推演中间表示（RenderScript）的完整类型定义。
这是前后端共享的数据契约，也是 Agent 产出的目标格式。

对齐设计文档 v1.0 第 5 节 + 开发任务第 4 节。
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ============================================================================
# 枚举类型
# ============================================================================


class AudienceEnum(StrEnum):
    """目标用户。"""
    UNDERGRADUATE_CS = "undergraduate_cs"
    GRADUATE_CS = "graduate_cs"
    HIGH_SCHOOL = "high_school"
    SELF_LEARNER = "self_learner"


class DifficultyEnum(StrEnum):
    """难度等级。"""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class VisualObjectType(StrEnum):
    """视觉对象类型（14 种）。"""
    NODE = "node"
    EDGE = "edge"
    ARRAY = "array"
    LINKED_LIST = "linked_list"
    TREE = "tree"
    GRAPH = "graph"
    TABLE = "table"
    CODE_BLOCK = "code_block"
    MEMORY_BLOCK = "memory_block"
    PROCESS = "process"
    TIMELINE = "timeline"
    FORMULA = "formula"
    CARD = "card"
    MINDMAP = "mindmap"


class AnimationType(StrEnum):
    """动画类型（16 种）。"""
    APPEAR = "appear"
    DISAPPEAR = "disappear"
    HIGHLIGHT = "highlight"
    TRANSFORM = "transform"
    MOVE = "move"
    UPDATE_VALUE = "update_value"
    COMPARE = "compare"
    SWAP = "swap"
    RELAX_EDGE = "relax_edge"
    ENQUEUE = "enqueue"
    DEQUEUE = "dequeue"
    SPLIT = "split"
    MERGE = "merge"
    SCHEDULE = "schedule"
    LOCK = "lock"
    UNLOCK = "unlock"


class InteractionType(StrEnum):
    """交互控件类型。"""
    SLIDER = "slider"
    SELECT = "select"
    SWITCH = "switch"
    BUTTON = "button"


class CheckType(StrEnum):
    """校验规则类型。"""
    DISTANCE_CONSISTENCY = "distance_consistency"
    STATE_CONSISTENCY = "state_consistency"
    INVARIANT = "invariant"
    BOUNDARY = "boundary"


class ParameterType(StrEnum):
    """参数类型。"""
    NUMBER = "number"
    STRING = "string"
    BOOLEAN = "boolean"
    ENUM = "enum"
    GRAPH = "graph"
    ARRAY = "array"
    CODE = "code"


class QualityStatus(StrEnum):
    """帧质量状态。"""
    PENDING = "pending"
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"


class ProjectStatus(StrEnum):
    """项目状态。"""
    DRAFT = "draft"
    PLANNING = "planning"
    GENERATING = "generating"
    REVIEWING = "reviewing"
    DONE = "done"


class ExportStatus(StrEnum):
    """导出任务状态。"""
    QUEUED = "queued"
    RENDERING = "rendering"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FeedbackType(StrEnum):
    """反馈类型。"""
    RATING = "rating"
    CORRECTION = "correction"
    SUGGESTION = "suggestion"


# ============================================================================
# 基础组件
# ============================================================================


class Position(BaseModel):
    """2D 坐标。"""
    x: float = 0.0
    y: float = 0.0


class Style(BaseModel):
    """视觉样式（自由 JSON，预定义常用字段）。"""
    color: str | None = None
    size: int | None = None
    width: int | None = None
    background_color: str | None = None
    border_color: str | None = None
    font_size: int | None = None
    opacity: float | None = None
    extras: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


# ============================================================================
# VisualObject — 14 种子类型的 discriminated union
# ============================================================================


class VisualObjectBase(BaseModel):
    """视觉对象基类。"""
    id: str = Field(..., description="对象唯一标识，如 'node_a'")
    label: str | None = None
    position: Position = Field(default_factory=Position)
    style: Style = Field(default_factory=Style)

    model_config = ConfigDict(extra="allow")


class NodeObject(VisualObjectBase):
    """圆形/方形节点。"""
    type: Literal[VisualObjectType.NODE] = VisualObjectType.NODE
    node_type: Literal["circle", "square", "diamond"] = "circle"


class EdgeObject(VisualObjectBase):
    """有向/无向边。"""
    type: Literal[VisualObjectType.EDGE] = VisualObjectType.EDGE
    source: str = Field(..., description="来源节点 id")
    target: str = Field(..., description="目标节点 id")
    directed: bool = True
    weight: float | None = None


class ArrayObject(VisualObjectBase):
    """数组/列表。"""
    type: Literal[VisualObjectType.ARRAY] = VisualObjectType.ARRAY
    cells: list[dict[str, Any]] = Field(default_factory=list)


class LinkedListObject(VisualObjectBase):
    """链表。"""
    type: Literal[VisualObjectType.LINKED_LIST] = VisualObjectType.LINKED_LIST
    nodes: list[dict[str, Any]] = Field(default_factory=list)


class TreeObject(VisualObjectBase):
    """树结构。"""
    type: Literal[VisualObjectType.TREE] = VisualObjectType.TREE
    root_id: str | None = None
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)


class GraphObject(VisualObjectBase):
    """图结构。"""
    type: Literal[VisualObjectType.GRAPH] = VisualObjectType.GRAPH
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    graph_edges: list[dict[str, Any]] = Field(
        default_factory=list,
        alias="edges",
    )

    model_config = ConfigDict(populate_by_name=True)


class TableObject(VisualObjectBase):
    """数据表格。"""
    type: Literal[VisualObjectType.TABLE] = VisualObjectType.TABLE
    headers: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)


class CodeBlockObject(VisualObjectBase):
    """代码块。"""
    type: Literal[VisualObjectType.CODE_BLOCK] = VisualObjectType.CODE_BLOCK
    language: str = "python"
    code: str = ""
    highlight_lines: list[int] = Field(default_factory=list)


class MemoryBlockObject(VisualObjectBase):
    """内存布局可视化。"""
    type: Literal[VisualObjectType.MEMORY_BLOCK] = VisualObjectType.MEMORY_BLOCK
    blocks: list[dict[str, Any]] = Field(default_factory=list)


class ProcessObject(VisualObjectBase):
    """进程控制块。"""
    type: Literal[VisualObjectType.PROCESS] = VisualObjectType.PROCESS
    pid: str | None = None
    state: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class TimelineObject(VisualObjectBase):
    """时间线。"""
    type: Literal[VisualObjectType.TIMELINE] = VisualObjectType.TIMELINE
    events: list[dict[str, Any]] = Field(default_factory=list)


class FormulaObject(VisualObjectBase):
    """LaTeX 公式。"""
    type: Literal[VisualObjectType.FORMULA] = VisualObjectType.FORMULA
    latex: str = ""


class CardObject(VisualObjectBase):
    """知识卡片。"""
    type: Literal[VisualObjectType.CARD] = VisualObjectType.CARD
    title: str = ""
    content: str = ""
    category: str | None = None


class MindmapObject(VisualObjectBase):
    """思维导图。"""
    type: Literal[VisualObjectType.MINDMAP] = VisualObjectType.MINDMAP
    root: dict[str, Any] = Field(default_factory=dict)
    children: list[dict[str, Any]] = Field(default_factory=list)


# discriminated union
VisualObject = Annotated[
    NodeObject
    | EdgeObject
    | ArrayObject
    | LinkedListObject
    | TreeObject
    | GraphObject
    | TableObject
    | CodeBlockObject
    | MemoryBlockObject
    | ProcessObject
    | TimelineObject
    | FormulaObject
    | CardObject
    | MindmapObject,
    Field(discriminator="type"),
]


# ============================================================================
# Animation — 16 种子类型的 discriminated union
# ============================================================================


class AnimationBase(BaseModel):
    """动画基类。"""
    target: str = Field(..., description="目标 VisualObject.id")
    duration_ms: int = 500
    params: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class AppearAnimation(AnimationBase):
    type: Literal[AnimationType.APPEAR] = AnimationType.APPEAR


class DisappearAnimation(AnimationBase):
    type: Literal[AnimationType.DISAPPEAR] = AnimationType.DISAPPEAR


class HighlightAnimation(AnimationBase):
    type: Literal[AnimationType.HIGHLIGHT] = AnimationType.HIGHLIGHT
    color: str = "#FFD700"


class TransformAnimation(AnimationBase):
    type: Literal[AnimationType.TRANSFORM] = AnimationType.TRANSFORM


class MoveAnimation(AnimationBase):
    type: Literal[AnimationType.MOVE] = AnimationType.MOVE
    from_position: Position | None = None
    to_position: Position | None = None


class UpdateValueAnimation(AnimationBase):
    type: Literal[AnimationType.UPDATE_VALUE] = AnimationType.UPDATE_VALUE
    from_value: Any = None
    to_value: Any = None


class CompareAnimation(AnimationBase):
    type: Literal[AnimationType.COMPARE] = AnimationType.COMPARE
    left: str = ""
    right: str = ""


class SwapAnimation(AnimationBase):
    type: Literal[AnimationType.SWAP] = AnimationType.SWAP
    target_2: str = ""


class RelaxEdgeAnimation(AnimationBase):
    type: Literal[AnimationType.RELAX_EDGE] = AnimationType.RELAX_EDGE
    new_weight: float | None = None


class EnqueueAnimation(AnimationBase):
    type: Literal[AnimationType.ENQUEUE] = AnimationType.ENQUEUE


class DequeueAnimation(AnimationBase):
    type: Literal[AnimationType.DEQUEUE] = AnimationType.DEQUEUE


class SplitAnimation(AnimationBase):
    type: Literal[AnimationType.SPLIT] = AnimationType.SPLIT


class MergeAnimation(AnimationBase):
    type: Literal[AnimationType.MERGE] = AnimationType.MERGE


class ScheduleAnimation(AnimationBase):
    type: Literal[AnimationType.SCHEDULE] = AnimationType.SCHEDULE


class LockAnimation(AnimationBase):
    type: Literal[AnimationType.LOCK] = AnimationType.LOCK


class UnlockAnimation(AnimationBase):
    type: Literal[AnimationType.UNLOCK] = AnimationType.UNLOCK


# discriminated union
Animation = Annotated[
    AppearAnimation
    | DisappearAnimation
    | HighlightAnimation
    | TransformAnimation
    | MoveAnimation
    | UpdateValueAnimation
    | CompareAnimation
    | SwapAnimation
    | RelaxEdgeAnimation
    | EnqueueAnimation
    | DequeueAnimation
    | SplitAnimation
    | MergeAnimation
    | ScheduleAnimation
    | LockAnimation
    | UnlockAnimation,
    Field(discriminator="type"),
]


# ============================================================================
# InteractionHook
# ============================================================================


class InteractionHook(BaseModel):
    """交互控件定义。"""
    type: InteractionType = InteractionType.BUTTON
    param: str = Field(..., description="绑定的参数 key")
    label: str | None = None
    range: list[float] | None = None       # slider 的 min/max
    options: list[str] | None = None       # select 的选项
    default: Any = None

    model_config = ConfigDict(extra="allow")


# ============================================================================
# Check (校验规则)
# ============================================================================


class Check(BaseModel):
    """帧级校验规则。"""
    type: CheckType = CheckType.STATE_CONSISTENCY
    rule: str = Field(..., description="校验表达式或描述")

    model_config = ConfigDict(extra="allow")


# ============================================================================
# Frame (核心)
# ============================================================================


class Frame(BaseModel):
    """推演帧 — 系统的核心数据单元。"""
    frame_id: str = Field(..., description="帧标识，如 'f_001'")
    title: str = ""
    learning_goal: str = ""
    narration: str = ""
    visual_objects: list[VisualObject] = Field(default_factory=list)
    state_snapshot: dict[str, Any] = Field(default_factory=dict)
    animations: list[Animation] = Field(default_factory=list)
    interaction_hooks: list[InteractionHook] = Field(default_factory=list)
    checks: list[Check] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


# ============================================================================
# TeachingStrategy, KnowledgeGraph
# ============================================================================


class TeachingStrategy(BaseModel):
    """教学策略。"""
    objectives: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    approach: str = ""
    difficulty_curve: str | None = None
    risk_notes: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class ConceptNode(BaseModel):
    """知识概念节点。"""
    id: str
    name: str
    type: str = "definition"         # definition / core_mechanism / example / theorem


class ConceptEdge(BaseModel):
    """概念关系边。"""
    source: str                      # from concept id
    target: str                      # to concept id
    relation: str = "leads_to"       # leads_to / depends_on / exemplifies


class KnowledgeGraph(BaseModel):
    """知识图谱。"""
    concepts: list[ConceptNode] = Field(default_factory=list)
    edges: list[ConceptEdge] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


# ============================================================================
# Parameter
# ============================================================================


class Parameter(BaseModel):
    """可调参数。"""
    key: str
    label: str
    param_type: ParameterType = ParameterType.NUMBER
    default_value: Any = None
    current_value: Any = None
    constraints: dict[str, Any] = Field(default_factory=dict)
    visibility: Literal["student", "teacher"] = "student"
    recompute_scope: Literal["local", "all_frames"] = "all_frames"

    model_config = ConfigDict(extra="allow")


# ============================================================================
# Asset (多模态资源)
# ============================================================================


class Asset(BaseModel):
    """多模态资源（知识卡片/思维导图/状态表 等的可复用描述）。"""
    id: str
    type: str                       # card / mindmap / table / code_snippet
    title: str | None = None
    content: dict[str, Any] = Field(default_factory=dict)
    related_frame_ids: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


# ============================================================================
# RenderScript (顶层 DSL)
# ============================================================================


class RenderScript(BaseModel):
    """教学推演中间表示（DSL）— 顶层结构。

    Agent 产出的完整推演描述。Web Renderer 和 Manim Adapter 各自消费。
    """
    project_id: str
    topic: str
    audience: AudienceEnum = AudienceEnum.UNDERGRADUATE_CS
    difficulty: DifficultyEnum = DifficultyEnum.INTERMEDIATE
    teaching_strategy: TeachingStrategy = Field(default_factory=TeachingStrategy)
    knowledge_graph: KnowledgeGraph = Field(default_factory=KnowledgeGraph)
    parameters: list[Parameter] = Field(default_factory=list)
    frames: list[Frame] = Field(default_factory=list)
    assets: list[Asset] = Field(default_factory=list)
    export_targets: list[Literal["web", "manim_video"]] = Field(
        default_factory=lambda: ["web", "manim_video"]
    )

    model_config = ConfigDict(extra="allow")
