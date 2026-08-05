"""Mindmap Generator — 思维导图生成器。

基于 knowledge_graph 概念节点和关系边，通过 LLM 生成层次化思维导图。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .base import BaseGenerator
from .registry import register_generator

logger = logging.getLogger(__name__)


MINIMAP_SYSTEM_PROMPT = """你是一位知识可视化专家，擅长将知识概念转化为层次分明的思维导图。

## 你的任务

根据教学计划和知识图谱，生成一份结构清晰、层次分明的思维导图。

## 设计原则

1. **根节点**：用户学习的主题/算法名称
2. **一级子节点**：核心概念（2-4个），每个是一个独立的知识单元
3. **二级子节点**：每个概念的要点（1-3个），如定义、特点、应用、误区
4. **三级子节点（可选）**：具体细节，如公式、例子、代码片段

## 节点命名规则

- 名称控制在 10 字以内，简洁明了
- 使用动词/名词/短语，不要完整句子
- 技术术语保持原文（如 Dijkstra、BFS、TCP）

## 输出格式

```json
{
  "root": {
    "name": "主题名称",
    "children": [
      {
        "name": "概念A",
        "type": "core_mechanism",
        "children": [
          {"name": "要点1", "children": []},
          {"name": "要点2", "children": []}
        ]
      },
      {
        "name": "概念B",
        "type": "definition",
        "children": [
          {"name": "要点1", "children": []}
        ]
      }
    ]
  },
  "metadata": {
    "total_nodes": 10,
    "max_depth": 3,
    "concepts_covered": ["概念A", "概念B"]
  }
}
```

## 约束

- 最多 3 层深度（含根节点）
- 总节点数 8-20 个
- 每个概念至少 1 个子节点
- 节点 type 从以下选取：definition、core_mechanism、prerequisite、comparison、extension、example
"""


MINDMAP_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "root": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "children": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "type": {"type": "string"},
                            "children": {"type": "array"},
                        },
                        "required": ["name", "children"],
                    },
                },
            },
            "required": ["name", "children"],
        },
        "metadata": {
            "type": "object",
            "properties": {
                "total_nodes": {"type": "integer"},
                "max_depth": {"type": "integer"},
                "concepts_covered": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
    "required": ["root"],
}


class MindmapGenerator(BaseGenerator):
    """思维导图生成器。

    输入 teaching_plan + knowledge_graph，输出层次化思维导图 JSON。
    """

    module_id = "mindmap"
    display_name = "思维导图"
    description = "生成知识概念导图，展示概念间的层次关系和知识结构"
    icon = "mindmap"
    category = "visual"
    priority = 1
    version = "1.0.0"

    temperature = 0.3
    max_tokens = 4096

    @property
    def output_schema(self) -> dict[str, Any]:
        return MINDMAP_OUTPUT_SCHEMA

    def get_system_prompt(self) -> str:
        return MINIMAP_SYSTEM_PROMPT

    def _build_context(
        self,
        teaching_plan: dict[str, Any],
        knowledge_graph: dict[str, Any],
        user_input: str,
        constraints: dict[str, Any],
    ) -> dict[str, Any]:
        """精简上下文：只传概念列表和教学大纲。"""
        concepts = knowledge_graph.get("concepts", [])
        concept_names = [c.get("name", "") for c in concepts]
        concept_types = {c.get("name", ""): c.get("type", "definition") for c in concepts}

        outline_steps = [
            s.get("title", "") for s in teaching_plan.get("outline", [])
        ]

        return {
            "topic": user_input,
            "concepts": [{"name": n, "type": concept_types.get(n, "definition")} for n in concept_names],
            "teaching_outline": outline_steps,
        }

    def validate(self, output: dict[str, Any]) -> list[dict[str, Any]]:
        """校验思维导图结构完整性。"""
        issues = super().validate(output)
        # 如果基类校验发现非 dict 等严重问题，直接返回
        if any(i["severity"] == "high" and i["type"] == "schema_error" for i in issues):
            return issues

        root = output.get("root", {})
        if not isinstance(root, dict):
            issues.append({
                "severity": "high",
                "type": "invalid_root",
                "description": f"思维导图 root 不是对象: {type(root).__name__}",
            })
            return issues
        if not root.get("name"):
            issues.append({
                "severity": "high",
                "type": "missing_root_name",
                "description": "思维导图根节点缺少 name",
            })

        children = root.get("children", [])
        if len(children) == 0:
            issues.append({
                "severity": "medium",
                "type": "empty_children",
                "description": "思维导图没有一级子节点，可能生成不完整",
            })

        # 检查深度
        def _max_depth(node: dict, depth: int = 1) -> int:
            kids = node.get("children", [])
            if not kids:
                return depth
            return max(_max_depth(c, depth + 1) for c in kids)

        depth = _max_depth(root)
        if depth > 4:
            issues.append({
                "severity": "low",
                "type": "deep_tree",
                "description": f"思维导图深度为 {depth}，建议不超过 3 层",
            })

        return issues


# ── 自动注册 ──────────────────────────────────────────────────

register_generator(MindmapGenerator())
logger.info("MindmapGenerator 已注册 (module_id=mindmap)")
