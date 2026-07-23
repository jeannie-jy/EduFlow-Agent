"""知识库 API 路由。

POST   /api/knowledge/search              语义检索 (pgvector + 关键词降级)
GET    /api/knowledge/templates            知识点模板列表
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_readonly_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

# 加载种子数据（降级备用）
_seed_path = Path(__file__).resolve().parent.parent / "data" / "seed_knowledge.json"
_seed_data: list[dict] = []

try:
    if _seed_path.exists():
        _seed_data = json.loads(_seed_path.read_text(encoding="utf-8"))
        logger.info("知识库种子数据加载: %d 条", len(_seed_data))
except Exception:
    logger.warning("知识库种子数据加载失败，搜索将返回空结果")


@router.post("/search")
async def search_knowledge(
    body: dict,
    session: AsyncSession = Depends(get_readonly_session),
) -> dict:
    """语义检索知识库。

    优先使用 pgvector 向量检索，不可用时降级为关键词匹配。
    """
    query = body.get("query", "")
    top_k = min(body.get("top_k", 5), 50)
    subject = body.get("subject")
    difficulty = body.get("difficulty")

    # 尝试 pgvector 检索
    try:
        from services.knowledge_service import search_knowledge_pgvector

        results = await search_knowledge_pgvector(
            query=query,
            top_k=top_k,
            subject=subject,
            difficulty=difficulty,
            session=session,
        )
        if results:
            return {"results": results}
    except Exception as exc:
        logger.warning("pgvector 检索失败，使用种子数据关键词匹配: %s", exc)

    # 降级：种子数据关键词匹配
    if not _seed_data:
        return {"results": []}

    query_lower = query.lower()
    scored = []
    for item in _seed_data:
        concept = item.get("concept", "")
        content = item.get("content", "")
        item_subject = item.get("subject", "")

        if subject and item_subject != subject:
            continue
        if difficulty is not None and item.get("difficulty") != difficulty:
            continue

        score = 0.0
        if query_lower in concept.lower():
            score = 0.95
        elif any(word in content.lower() for word in query_lower.split()):
            score = 0.7
        elif query_lower in item_subject.lower():
            score = 0.5
        else:
            score = 0.1

        scored.append({
            "id": concept,
            "concept": concept,
            "content": content[:500],
            "subject": item_subject,
            "difficulty": item.get("difficulty", 3),
            "similarity": score,
            "object_types": item.get("object_types", []),
            "animation_types": item.get("animation_types", []),
        })

    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return {"results": scored[:top_k]}


@router.get("/templates")
async def list_templates(
    subject: str | None = Query(default=None),
    difficulty: int | None = Query(default=None, ge=1, le=5),
) -> dict:
    """获取知识点模板列表。"""
    templates = _seed_data

    if subject:
        templates = [t for t in templates if t.get("subject") == subject]
    if difficulty is not None:
        templates = [t for t in templates if t.get("difficulty") == difficulty]

    return {
        "templates": [
            {
                "id": t.get("concept", ""),
                "concept": t.get("concept", ""),
                "subject": t.get("subject"),
                "difficulty": t.get("difficulty", 3),
                "object_types": t.get("object_types", []),
            }
            for t in templates
        ],
    }
