"""design_parameters Tool — 参数设计 Agent。

根据知识点类型和上下文，生成可调参数定义。
设计文档 Section 4.1 + 需求文档 8.5 节。
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── 按知识点类型的参数模板 ──────────────────────────────────

_PARAMETER_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "algorithm": [
        {
            "key": "input_size",
            "label": "输入规模",
            "param_type": "number",
            "default_value": 8,
            "constraints": {"min": 3, "max": 100, "step": 1},
            "visibility": "student",
            "recompute_scope": "all_frames",
        },
        {
            "key": "show_pseudocode",
            "label": "显示伪代码",
            "param_type": "boolean",
            "default_value": True,
            "constraints": {},
            "visibility": "student",
            "recompute_scope": "local",
        },
        {
            "key": "animation_speed",
            "label": "动画速度",
            "param_type": "number",
            "default_value": 1.0,
            "constraints": {"min": 0.25, "max": 3.0, "step": 0.25},
            "visibility": "student",
            "recompute_scope": "local",
        },
    ],
    "data_structure": [
        {
            "key": "initial_values",
            "label": "初始数据",
            "param_type": "array",
            "default_value": [5, 3, 8, 1, 9, 2],
            "constraints": {"min_length": 3, "max_length": 50},
            "visibility": "student",
            "recompute_scope": "all_frames",
        },
        {
            "key": "show_pointers",
            "label": "显示指针/引用",
            "param_type": "boolean",
            "default_value": True,
            "constraints": {},
            "visibility": "teacher",
            "recompute_scope": "local",
        },
    ],
    "operating_system": [
        {
            "key": "process_count",
            "label": "进程数量",
            "param_type": "number",
            "default_value": 4,
            "constraints": {"min": 2, "max": 10, "step": 1},
            "visibility": "student",
            "recompute_scope": "all_frames",
        },
        {
            "key": "time_quantum",
            "label": "时间片大小",
            "param_type": "number",
            "default_value": 3,
            "constraints": {"min": 1, "max": 10, "step": 1},
            "visibility": "student",
            "recompute_scope": "all_frames",
        },
        {
            "key": "scheduling_algorithm",
            "label": "调度算法",
            "param_type": "enum",
            "default_value": "round_robin",
            "constraints": {"options": ["fcfs", "sjf", "round_robin", "priority", "mlfq"]},
            "visibility": "teacher",
            "recompute_scope": "all_frames",
        },
    ],
    "computer_network": [
        {
            "key": "topology",
            "label": "网络拓扑",
            "param_type": "enum",
            "default_value": "star",
            "constraints": {"options": ["star", "mesh", "bus", "ring"]},
            "visibility": "student",
            "recompute_scope": "all_frames",
        },
        {
            "key": "packet_loss_rate",
            "label": "丢包率",
            "param_type": "number",
            "default_value": 0.0,
            "constraints": {"min": 0.0, "max": 0.5, "step": 0.05},
            "visibility": "teacher",
            "recompute_scope": "all_frames",
        },
    ],
    "database": [
        {
            "key": "table_size",
            "label": "表规模（行数）",
            "param_type": "number",
            "default_value": 10,
            "constraints": {"min": 3, "max": 50, "step": 1},
            "visibility": "student",
            "recompute_scope": "all_frames",
        },
        {
            "key": "isolation_level",
            "label": "隔离级别",
            "param_type": "enum",
            "default_value": "read_committed",
            "constraints": {
                "options": [
                    "read_uncommitted",
                    "read_committed",
                    "repeatable_read",
                    "serializable",
                ]
            },
            "visibility": "teacher",
            "recompute_scope": "all_frames",
        },
    ],
}


async def design_parameters(
    knowledge_type: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """根据知识点类型生成参数定义。

    对于已知的知识点类型，使用预定义模板 + 上下文字段填充。
    对于未知类型，使用 LLM 生成。

    Args:
        knowledge_type: 知识点类型
        context: 教学上下文

    Returns:
        {"parameters": [...]}
    """
    ctx = context or {}

    # 查找模板
    templates = _PARAMETER_TEMPLATES.get(knowledge_type, [])

    if templates:
        # 从模板生成，根据 context 调整默认值
        parameters = []
        for tmpl in templates:
            param = dict(tmpl)
            # 上下文覆盖
            if tmpl["key"] in ctx:
                param["default_value"] = ctx[tmpl["key"]]
            parameters.append(param)
        return {"parameters": parameters}

    # 兜底：通用参数
    logger.info("未知知识点类型 '%s'，使用通用参数模板", knowledge_type)
    return {
        "parameters": [
            {
                "key": "input_data",
                "label": "输入数据",
                "param_type": "array",
                "default_value": ctx.get("input_data", []),
                "constraints": {},
                "visibility": "student",
                "recompute_scope": "all_frames",
            },
            {
                "key": "show_details",
                "label": "显示详细信息",
                "param_type": "boolean",
                "default_value": True,
                "constraints": {},
                "visibility": "student",
                "recompute_scope": "local",
            },
            {
                "key": "animation_speed",
                "label": "动画速度",
                "param_type": "number",
                "default_value": 1.0,
                "constraints": {"min": 0.25, "max": 3.0, "step": 0.25},
                "visibility": "student",
                "recompute_scope": "local",
            },
        ],
    }
