"""Knowledge Cards Generator — 知识卡片生成器。

为 knowledge_graph 中的每个概念生成结构化的知识卡片：
定义、直觉理解、常见误区、公式、伪代码。
"""

from __future__ import annotations

import logging
from typing import Any

from .base import BaseGenerator
from .registry import register_generator

logger = logging.getLogger(__name__)


CARD_SYSTEM_PROMPT = """你是一位教学资源设计专家，擅长将知识概念提炼为简洁、直观的知识卡片。

## 你的任务

根据教学计划和知识图谱，为每个核心概念生成一张知识卡片。

## 卡片内容规范

每张卡片包含以下字段：

- **title**：概念名称（10字以内）
- **definition**：一句话定义（30-60字），用通俗语言解释这是什么
- **intuition**：直观理解（20-50字），用一个比喻或类比帮助理解
- **pitfalls**：常见误区（1-3条），学生容易犯的错误或混淆点
- **formula**：关键公式（可选，LaTeX 格式）
- **pseudocode**：伪代码（可选，算法类概念提供）
- **category**：卡片分类（core_concept / mechanism / example / theorem / pitfall）
- **difficulty**：难度等级 1-5（1=入门, 3=中等, 5=进阶）

## 设计原则

1. **卡片独立可读**：每张卡片应能独立理解，不依赖前后卡片
2. **语言通俗**：避免过度学术化的表述，用日常语言解释
3. **重点突出**：definition 和 intuition 是核心，必须填写
4. **误区有价值**：pitfalls 应反映真实教学中的常见问题

## 输出格式

```json
{
  "cards": [
    {
      "id": "card_概念名",
      "title": "概念名称",
      "definition": "一句话定义...",
      "intuition": "直观类比...",
      "pitfalls": ["误区1", "误区2"],
      "formula": "LaTeX公式或null",
      "pseudocode": "伪代码或null",
      "category": "core_concept",
      "difficulty": 2
    }
  ]
}
```

## 约束

- 为 knowledge_graph 中的每个核心概念生成一张卡片（5-8张）
- definition 必填，30-80字
- pitfalls 至少 1 条（如果确实没有，用 []）
- formula/pseudocode 为 null 时输出 null，不要输出空字符串
"""


CARDS_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "cards": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "definition": {"type": "string"},
                    "intuition": {"type": "string"},
                    "pitfalls": {"type": "array", "items": {"type": "string"}},
                    "formula": {"type": ["string", "null"]},
                    "pseudocode": {"type": ["string", "null"]},
                    "category": {"type": "string"},
                    "difficulty": {"type": "integer"},
                },
                "required": ["id", "title", "definition", "intuition", "pitfalls"],
            },
        },
    },
    "required": ["cards"],
}


class CardGenerator(BaseGenerator):
    """知识卡片生成器。

    为 knowledge_graph 中的每个概念生成结构化知识卡片。
    """

    module_id = "cards"
    display_name = "知识卡片"
    description = "为每个核心概念生成知识卡片，包含定义、直觉理解和常见误区"
    icon = "cards"
    category = "visual"
    priority = 2
    version = "1.0.0"

    temperature = 0.3
    max_tokens = 8192

    @property
    def output_schema(self) -> dict[str, Any]:
        return CARDS_OUTPUT_SCHEMA

    def get_system_prompt(self) -> str:
        return CARD_SYSTEM_PROMPT

    def _build_context(
        self,
        teaching_plan: dict[str, Any],
        knowledge_graph: dict[str, Any],
        user_input: str,
        constraints: dict[str, Any],
    ) -> dict[str, Any]:
        """将概念列表和教学目标传给 LLM。"""
        concepts = knowledge_graph.get("concepts", [])
        simple_concepts = [
            {
                "id": c.get("id", ""),
                "name": c.get("name", ""),
                "type": c.get("type", "definition"),
                "description": c.get("description", ""),
                "pitfalls_hint": c.get("common_pitfalls", []),
            }
            for c in concepts
        ]

        return {
            "topic": user_input,
            "objectives": teaching_plan.get("objectives", []),
            "concepts": simple_concepts,
        }

    def validate(self, output: dict[str, Any]) -> list[dict[str, Any]]:
        """校验卡片内容完整性。"""
        issues = super().validate(output)

        cards = output.get("cards", [])
        if len(cards) == 0:
            issues.append({
                "severity": "high",
                "type": "empty_cards",
                "description": "未生成任何知识卡片",
            })
            return issues

        for i, card in enumerate(cards):
            card_id = card.get("id", f"card_{i}")
            # 必填字段检查
            for field in ("title", "definition", "intuition"):
                if not card.get(field):
                    issues.append({
                        "severity": "medium",
                        "type": "missing_field",
                        "description": f"卡片 {card_id} 缺少 {field}",
                    })
            # definition 长度检查
            definition = card.get("definition", "")
            if len(definition) < 10:
                issues.append({
                    "severity": "warn",
                    "type": "short_definition",
                    "description": f"卡片 {card_id} 的 definition 过短 ({len(definition)} 字符)",
                })
            # pitfalls 至少 1 条（warn 级别）
            pitfalls = card.get("pitfalls", [])
            if isinstance(pitfalls, list) and len(pitfalls) == 0:
                issues.append({
                    "severity": "warn",
                    "type": "no_pitfalls",
                    "description": f"卡片 {card_id} 没有标注常见误区",
                })

        return issues


# ── 自动注册 ──────────────────────────────────────────────────

register_generator(CardGenerator())
logger.info("CardGenerator 已注册 (module_id=cards)")
