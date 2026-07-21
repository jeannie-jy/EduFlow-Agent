"""LangGraph AgentState 定义。

所有 Agent 在同一 LangGraph 进程内通过 TypedDict State 共享上下文。
对齐设计文档 3.3 节。
"""

from __future__ import annotations

from typing import TypedDict


class AgentState(TypedDict, total=False):
    """多 Agent 共享状态。

    字段按 Agent 分组，由各节点读写。LangGraph checkpointer 负责持久化。
    """

    # ── 用户输入 ──────────────────────────────────────────
    user_input: str
    materials: list[dict]              # 上传材料解析结果
    constraints: dict                  # 教师约束

    # ── Planner 产出 ─────────────────────────────────────
    teaching_plan: dict                # 教学目标、大纲、策略

    # ── Knowledge 产出 ───────────────────────────────────
    knowledge_graph: dict              # 概念节点 + 关系边
    key_terms: list[str]

    # ── Coder 产出 ───────────────────────────────────────
    dsl: dict                          # 完整 RenderScript

    # ── Quality 产出 ─────────────────────────────────────
    quality_report: dict               # 评分 + 问题列表

    # ── Reflection 状态 ──────────────────────────────────
    reflection_count: int
    revision_history: list[dict]

    # ── Human-in-the-Loop ────────────────────────────────
    pending_approval: str | None       # 等待审批的内容
    approval_mode: bool                # plan_only 模式时启用审批
    user_feedback: dict | None         # 用户反馈

    # ── 元信息 ───────────────────────────────────────────
    project_id: str
    status: str                        # drafting / planning / generating / reviewing / done
