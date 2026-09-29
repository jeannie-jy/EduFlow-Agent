"""知识库 API 路由。

POST   /api/knowledge/search              语义检索 (pgvector + 关键词降级)
GET    /api/knowledge/templates            知识点模板列表
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_readonly_session
from db.models import Project, User
from config import get_settings
from .auth import get_current_user, is_admin

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
    current_user: User | None = Depends(get_current_user),
) -> dict:
    """语义检索知识库。

    优先使用 pgvector 向量检索，不可用时降级为关键词匹配。
    """
    query = str(body.get("query") or "").strip()
    if not query:
        return {"results": []}
    try:
        top_k = min(max(int(body.get("top_k", 5)), 1), 50)
    except (TypeError, ValueError):
        top_k = 5
    subject = body.get("subject")
    difficulty = body.get("difficulty")

    if get_settings().knowledge_v2_enabled:
        from fastapi import HTTPException
        from services.knowledge_library import search_library

        project_id = None
        owner_id = current_user.id if current_user else None
        if body.get("project_id"):
            try:
                project_id = uuid.UUID(str(body["project_id"]))
            except ValueError as exc:
                raise HTTPException(status_code=422, detail="Invalid project ID") from exc
            project = await session.get(Project, project_id)
            if project is None or (not is_admin(current_user) and str(project.owner_id) != str(owner_id)):
                raise HTTPException(status_code=404, detail="Project not found")
            owner_id = uuid.UUID(project.owner_id) if project.owner_id else None
        return {"results": await search_library(
            session, query, top_k=top_k, project_id=project_id, owner_id=owner_id,
            subject=subject, difficulty=difficulty,
        )}

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

    from services.knowledge_service import _lexical_search_terms

    query_lower = query.lower()
    terms = _lexical_search_terms(query)
    if not terms:
        return {"results": []}
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
        if len(query_lower) >= 2 and query_lower in concept.lower():
            score = 0.95
        elif any(term in concept.lower() for term in terms):
            score = 0.8
        elif any(term in content.lower() for term in terms):
            score = 0.7
        else:
            continue

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
