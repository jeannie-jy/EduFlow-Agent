"""Misconception Gallery Generator — 常见误区生成器。

为 knowledge_graph 中的核心概念生成常见的理解误区，
以「错误→正确→反例」结构帮助学生纠正认知偏差。
"""

from __future__ import annotations

import logging
from typing import Any

from .base import BaseGenerator
from .registry import register_generator

logger = logging.getLogger(__name__)

MISCONCEPTION_SYSTEM_PROMPT = """你是一位教学诊断专家，擅长识别和纠正学生对计算机科学概念的常见误解。

## 你的任务

根据教学计划和知识图谱，为每个核心概念生成 1-2 个常见误区（misconception），
帮助学生意识到并纠正自己的认知偏差。

## 每个误区结构

- **misconception**：错误的理解（学生真实会犯的错误，不是捏造的）
- **correction**：正确的理解（言简意赅，直接纠正）
- **counter_example**：一个反例来说明为什么错误理解会导致问题
- **why_it_matters**：为什么纠正这个误区很重要（一句话）

## 输出格式

```json
{
  "items": [
    {
      "id": "m1",
      "concept": "Dijkstra 算法",
      "related_concept_id": "c1",
      "misconception": "Dijkstra 算法和 BFS 是等价的，只是权重不同",
      "correction": "Dijkstra 是贪心最短路径算法，BFS 是等权图的最短路径特例。Dijkstra 需要优先队列处理不同权重，而 BFS 只需普通队列。",
      "counter_example": "在一条边权为 10、另一条边权为 1 的图中，BFS 会走边更少的路径而非权更小的路径，导致错误结果。",
      "why_it_matters": "理解两者区别有助于在正确场景选择合适的算法，避免在加权图中误用 BFS。",
      "difficulty": 2
    },
    {
      "id": "m2",
      "concept": "NP 完全性",
      "related_concept_id": "c3",
      "misconception": "NP 代表 'Not Polynomial'（非多项式时间）",
      "correction": "NP 代表 'Nondeterministic Polynomial'（非确定性多项式）。NP 问题可以在多项式时间内验证解，但不一定能在多项式时间内求解。",
      "counter_example": "排序问题在 P 中（可在多项式时间求解），也在 NP 中（解可在多项式时间验证），所以 NP 不等于'不能在多项式时间求解'。",
      "why_it_matters": "正确理解 NP 的定义是理解 P vs NP 千年难题的基础。",
      "difficulty": 3
    }
  ],
  "metadata": {
    "total": 4,
    "concepts_covered": ["c1", "c2", "c3"]
  }
}
```

## 约束

- 每个核心概念 1-2 个误区
- 总共 3-8 个误区
- misconception 必须基于真实教学经验，不能编造不存在的误区
- correction 必须准确、不含歧义
- counter_example 必须具体、可验证
"""

MISCONCEPTION_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "concept": {"type": "string"},
                    "related_concept_id": {"type": "string"},
                    "misconception": {"type": "string"},
                    "correction": {"type": "string"},
                    "counter_example": {"type": "string"},
                    "why_it_matters": {"type": "string"},
                    "difficulty": {"type": "integer", "minimum": 1, "maximum": 3},
                },
                "required": ["id", "concept", "misconception", "correction"],
            },
        },
        "metadata": {"type": "object"},
    },
    "required": ["items"],
}


class MisconceptionGenerator(BaseGenerator):
    module_id = "misconception"
    display_name = "常见误区"
    description = "识别常见理解误区，用错误→正确→反例的结构帮助纠正认知偏差"
    icon = "misconception"
    category = "visual"
    priority = 7
    version = "1.0.0"
    temperature = 0.3
    max_tokens = 8192

    @property
    def output_schema(self) -> dict[str, Any]:
        return MISCONCEPTION_OUTPUT_SCHEMA

    def get_system_prompt(self) -> str:
        return MISCONCEPTION_SYSTEM_PROMPT

    def _build_context(self, teaching_plan, knowledge_graph, user_input, constraints):
        concepts = knowledge_graph.get("concepts", [])
        return {
            "topic": user_input,
            "concepts": [{"id": c.get("id"), "name": c.get("name"), "type": c.get("type"),
                          "pitfalls_hint": c.get("common_pitfalls", [])} for c in concepts],
            "objectives": teaching_plan.get("objectives", []),
        }

    def validate(self, output):
        issues = super().validate(output)
        if any(i["severity"] == "high" and i["type"] == "schema_error" for i in issues):
            return issues
        items = output.get("items", [])
        if not isinstance(items, list):
            issues.append({"severity": "high", "type": "invalid_items", "description": f"items 应为列表"})
            return issues
        if len(items) == 0:
            issues.append({"severity": "high", "type": "empty_items", "description": "未生成任何误区"})
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            iid = item.get("id", f"item_{i}")
            if not item.get("misconception"):
                issues.append({"severity": "medium", "type": "missing_misconception", "description": f"{iid} 缺少 misconception"})
            if not item.get("correction"):
                issues.append({"severity": "medium", "type": "missing_correction", "description": f"{iid} 缺少 correction"})
            if len(item.get("correction", "")) < 10:
                issues.append({"severity": "warn", "type": "short_correction", "description": f"{iid} 的 correction 过短"})
        return issues


register_generator(MisconceptionGenerator())
logger.info("MisconceptionGenerator 已注册 (module_id=misconception)")
