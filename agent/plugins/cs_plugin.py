"""CS 领域插件（内置）。

计算机科学是 MVP 的第一个也是唯一的内置插件。
包含：数据结构、算法、操作系统、网络、数据库、软件工程的教学模板。

对齐：设计文档 v1.0 Section 8.3。
"""

from __future__ import annotations

from typing import Any


class CSDomainPlugin:
    """计算机科学领域插件。

    实现 DomainPlugin 协议的所有方法。
    作为系统内置插件，在应用启动时自动注册。
    """

    domain_name = "computer_science"
    version = "1.0.0"
    display_name = "计算机科学"

    # ── 知识模板 ────────────────────────────────────────────

    def get_knowledge_templates(self) -> list[dict[str, Any]]:
        return [
            {
                "concept": "冒泡排序",
                "content": "冒泡排序是一种简单的比较排序算法...",
                "subject": "algorithm",
                "difficulty": 1,
                "object_types": ["array", "code_block"],
                "animation_types": ["compare", "swap", "highlight", "appear"],
            },
            # 其余 21 个模板在 data/seed_knowledge.json 中定义
            # 此处只列出签名，完整数据从 JSON 加载
        ]

    # ── 可视化对象 ──────────────────────────────────────────

    def get_visual_objects(self) -> dict[str, dict[str, Any]]:
        return {
            "node": {
                "description": "带标签的圆形/方形节点",
                "default_style": {"color": "#4A90D9", "size": 40},
            },
            "edge": {
                "description": "有向/无向边，带权重标签",
                "default_style": {"color": "#8892B0", "width": 2},
            },
            "array": {
                "description": "数组/列表，单元格可高亮",
                "default_style": {},
            },
            "tree": {
                "description": "树结构，支持旋转动画",
                "default_style": {},
            },
            "graph": {
                "description": "图结构，支持自动布局和拖拽",
                "default_style": {},
            },
            "table": {
                "description": "数据表格，单元格可高亮",
                "default_style": {},
            },
            "code_block": {
                "description": "代码块，支持语法高亮和逐行标记",
                "default_style": {"language": "python"},
            },
            "memory_block": {
                "description": "内存地址可视化",
                "default_style": {},
            },
            "process": {
                "description": "进程控制块/进程表示",
                "default_style": {"color": "#4A90D9"},
            },
            "timeline": {
                "description": "时间线/Gantt 图",
                "default_style": {},
            },
            "linked_list": {
                "description": "链表，节点+指针连线",
                "default_style": {},
            },
            "formula": {
                "description": "LaTeX 数学公式",
                "default_style": {},
            },
            "card": {
                "description": "知识概念卡片",
                "default_style": {},
            },
            "mindmap": {
                "description": "思维导图树形结构",
                "default_style": {},
            },
        }

    # ── 参数规则 ────────────────────────────────────────────

    def get_parameter_rules(self, knowledge_type: str) -> list[dict[str, Any]]:
        from tools.design_parameters import _PARAMETER_TEMPLATES
        return _PARAMETER_TEMPLATES.get(knowledge_type, [])

    # ── 教学策略 ────────────────────────────────────────────

    def get_teaching_strategies(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "直觉先行",
                "approach": "先直观演示 → 引入概念 → 伪代码对应 → 逐帧推演",
                "suitable_for": ["algorithm", "data_structure"],
                "difficulty_range": [1, 3],
            },
            {
                "name": "问题驱动",
                "approach": "提出问题 → 分析需求 → 设计方案 → 逐步实现",
                "suitable_for": ["operating_system", "computer_network"],
                "difficulty_range": [2, 4],
            },
            {
                "name": "对比分析",
                "approach": "展示多种方案 → 逐方案推演 → 对比优劣 → 总结",
                "suitable_for": ["algorithm", "database"],
                "difficulty_range": [3, 5],
            },
            {
                "name": "概念→实例",
                "approach": "定义概念 → 生活类比 → 技术实现 → 交互演示",
                "suitable_for": ["software_engineering"],
                "difficulty_range": [1, 3],
            },
            {
                "name": "逐层深入",
                "approach": "表层理解 → 深入机制 → 边界条件 → 进阶延伸",
                "suitable_for": ["operating_system", "computer_network", "database"],
                "difficulty_range": [3, 5],
            },
        ]

    # ── 质量规则 ────────────────────────────────────────────

    def get_quality_rules(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "algorithm_correctness",
                "rule": "验证算法步骤是否符合规范定义",
                "severity": "high",
                "description": "排序算法中的比较-交换逻辑，图算法的松弛操作",
            },
            {
                "type": "tree_balance",
                "rule": "检查旋转后 AVL/红黑树性质是否满足",
                "severity": "high",
                "description": "AVL 平衡因子 ≤1，红黑树黑高一致",
            },
            {
                "type": "state_consistency",
                "rule": "检查帧间状态变量是否自洽",
                "severity": "high",
                "description": "距离表不应无缘无故退化，数组不丢失元素",
            },
            {
                "type": "os_schedule_validity",
                "rule": "检查调度序列是否与算法定义一致",
                "severity": "medium",
                "description": "RR 的时间片切换，优先级调度的抢占逻辑",
            },
            {
                "type": "network_protocol_validity",
                "rule": "检查协议握手/挥手流程",
                "severity": "medium",
                "description": "TCP 三次握手顺序，SYN/ACK 标志位",
            },
            {
                "type": "code_syntax",
                "rule": "检查生成的伪代码语法正确性",
                "severity": "low",
                "description": "关键词拼写、缩进一致性",
            },
        ]
