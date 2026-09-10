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
    enable_retrieval: bool             # 主链是否调用知识库检索
    enable_tools: bool                 # 是否允许模型在受控 Registry 中选择只读工具

    # ── Planner 产出 ─────────────────────────────────────
    teaching_plan: dict                # 教学目标、大纲、策略

    # ── Knowledge 产出 ───────────────────────────────────
    knowledge_graph: dict              # 概念节点 + 关系边
    key_terms: list[str]
    retrieval: dict                    # 检索状态、来源 ID 和证据片段
    tool_calls: list[dict]             # 有界 Tool Calling 执行记录（不含敏感原文）

    # ── Coder 产出 ───────────────────────────────────────
    dsl: dict                          # 完整 RenderScript
    raw_coder_output: dict              # 归一化前的有界 Coder 输出（仅用于审计）
    coder_batch_mode: bool             # Coder 是否按小批次生成帧，避免单次超长 JSON

    # ── Quality 产出 ─────────────────────────────────────
    quality_report: dict               # 评分 + 问题列表

    # ── Reflection 状态 ──────────────────────────────────
    reflection_count: int
    revision_history: list[dict]

    # ── Human-in-the-Loop ────────────────────────────────
    pending_approval: str | None       # 等待审批的内容
    approval_mode: bool                # plan_only 模式时启用审批
    plan_rejected: bool                # 教学计划被拒绝 → 结束流程等前端重启
    user_feedback: dict | None         # 用户反馈
    replan_count: int                  # 图内重新规划次数
    workflow_entry: str                # planner / knowledge / coder / reflection
    regenerate_scope: dict             # 局部重生成范围
    locked_frame_ids: list[str]        # DB 锁定帧 + 当前局部操作的范围外保护帧

    # ── 模块选择（Phase A: 模块化生成器）─────────────────
    selected_modules: list[str]         # 用户选择的模块列表: ["mindmap","cards","frames"]
    module_outputs: dict[str, dict]     # module_id → 模块产出字典
    module_errors: dict[str, str]       # module_id → 错误信息
    ensure_frames: bool                 # 初次模块生成是否自动补充基础 Frames
    module_context_outputs: dict[str, dict]  # 单模块重生成时只读的既有依赖产物

    # ── 元信息 ───────────────────────────────────────────
    project_id: str
    actor_id: str | None                 # 服务端认证上下文，永不由模型参数提供
    actor_role: str | None
    status: str                        # drafting / planning / generating / reviewing / done
