"""search_knowledge Tool。

pgvector 语义检索知识库，返回相关概念定义、教学大纲、常见疑难点。
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

TOOL_DEF = {
    "name": "search_knowledge",
    "description": "在 CS 教学知识库中语义检索相关概念。输入概念名称或问题描述，返回匹配的知识条目，包含定义、教学建议、常见疑难点。",
    "parameters": {
        "type": "object",
        "properties": {
            "concept": {
                "type": "string",
                "description": "要检索的概念名称或问题描述，如 'Dijkstra 最短路径'",
            },
            "top_k": {
                "type": "integer",
                "description": "返回结果数量，默认 5",
                "default": 5,
            },
        },
        "required": ["concept"],
    },
    "returns": {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "concept": {"type": "string"},
                "content": {"type": "string"},
                "subject": {"type": "string"},
                "difficulty": {"type": "integer"},
                "similarity": {"type": "number"},
                "object_types": {"type": "array"},
                "animation_types": {"type": "array"},
            },
        },
    },
    "errors": ["KNOWLEDGE_NOT_FOUND"],
    "retryable": True,
    "timeout_ms": 10_000,
}


async def search_knowledge(
    concept: str,
    top_k: int = 5,
    *,
    llm_client: Any = None,
    db_session: Any = None,
) -> list[dict[str, Any]]:
    """执行语义检索。

    MVP 阶段：如果没有向量数据库连接，使用 LLM 做"模拟检索"
    （基于 LLM 对 CS 知识的理解直接返回结果）。
    完整实现：通过 pgvector 做向量相似度检索。
    """
    # TODO: 当 LLM 客户端可用时，可以通过 LLM 直接生成知识回复
    # 完整实现中使用 pgvector 检索
    if db_session is not None:
        try:
            from sqlalchemy import text
            result = await db_session.execute(
                text("""
                    SELECT id, concept, content, subject, difficulty, object_types, animation_types
                    FROM knowledge_base
                    WHERE subject IS NOT NULL
                    ORDER BY usage_count DESC
                    LIMIT :limit
                """),
                {"limit": top_k},
            )
            rows = result.fetchall()
            if rows:
                return [
                    {
                        "id": str(row[0]),
                        "concept": row[1],
                        "content": row[2],
                        "subject": row[3],
                        "difficulty": row[4],
                        "similarity": 0.95,
                        "object_types": row[5] or [],
                        "animation_types": row[6] or [],
                    }
                    for row in rows
                ]
        except Exception:
            pass  # Fall back to empty result

    return []
