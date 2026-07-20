"""generate_asset Tool — 多模态资源 Agent。

根据上下文生成知识卡片、思维导图、状态表、伪代码等资源描述。
设计文档 Section 4.1 + 需求文档 8.6 节。
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

TOOL_DEF_GENERATE_ASSET = {
    "name": "generate_asset",
    "description": "根据资源类型和上下文生成多模态教学资源：知识卡片、思维导图、状态表、伪代码区块。",
    "parameters": {
        "type": "object",
        "properties": {
            "asset_type": {
                "type": "string",
                "description": "资源类型: card / mindmap / table / code_snippet",
                "enum": ["card", "mindmap", "table", "code_snippet"],
            },
            "context": {
                "type": "object",
                "description": "生成上下文：概念名称、知识点描述、关联帧 ID 等",
            },
        },
        "required": ["asset_type", "context"],
    },
    "returns": {
        "type": "object",
        "properties": {
            "asset": {"type": "object"},
        },
    },
    "errors": [],
    "retryable": True,
    "timeout_ms": 30_000,
}


async def generate_asset(
    asset_type: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """生成单个多模态资源描述。

    Args:
        asset_type: 资源类型
        context: 生成上下文

    Returns:
        {"asset": {...}}
    """
    ctx = context or {}
    concept = ctx.get("concept", "Unknown")
    description = ctx.get("description", "")
    related_frame_ids = ctx.get("related_frame_ids", [])

    if asset_type == "card":
        return {
            "asset": {
                "id": f"card_{concept.lower().replace(' ', '_')}",
                "type": "card",
                "title": concept,
                "content": {
                    "definition": ctx.get("definition", description[:200]),
                    "intuition": ctx.get("intuition", ""),
                    "pitfalls": ctx.get("pitfalls", []),
                    "formula": ctx.get("formula"),
                    "pseudocode": ctx.get("pseudocode"),
                    "category": ctx.get("category", "core_concept"),
                },
                "related_frame_ids": related_frame_ids,
            }
        }

    if asset_type == "mindmap":
        return {
            "asset": {
                "id": f"mindmap_{concept.lower().replace(' ', '_')}",
                "type": "mindmap",
                "title": f"{concept} 概念导图",
                "content": {
                    "root": {
                        "id": "root",
                        "name": concept,
                        "type": "definition",
                        "children": ctx.get("children", []),
                    },
                },
                "related_frame_ids": related_frame_ids,
            }
        }

    if asset_type == "table":
        return {
            "asset": {
                "id": f"table_{concept.lower().replace(' ', '_')}",
                "type": "table",
                "title": ctx.get("title", f"{concept} 状态表"),
                "content": {
                    "headers": ctx.get("headers", []),
                    "rows": ctx.get("rows", []),
                },
                "related_frame_ids": related_frame_ids,
            }
        }

    if asset_type == "code_snippet":
        return {
            "asset": {
                "id": f"code_{concept.lower().replace(' ', '_')}",
                "type": "code_block",
                "title": ctx.get("title", f"{concept} 伪代码"),
                "content": {
                    "language": ctx.get("language", "python"),
                    "code": ctx.get("code", ""),
                    "highlight_lines": ctx.get("highlight_lines", []),
                },
                "related_frame_ids": related_frame_ids,
            }
        }

    logger.warning("未知资源类型: %s", asset_type)
    return {
        "asset": {
            "id": f"unknown_{concept.lower().replace(' ', '_')}",
            "type": "card",
            "title": concept,
            "content": {},
            "related_frame_ids": related_frame_ids,
        }
    }
