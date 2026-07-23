"""知识库服务 — pgvector 向量检索。

提供:
- 从 seed_knowledge.json 生成 embedding 并写入 knowledge_base 表
- 语义搜索（pgvector 余弦距离）
- 降级：pgvector 不可用时回退到关键词匹配
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from agents.llm_client import generate_embedding
from config import get_settings

logger = logging.getLogger(__name__)


async def search_knowledge_pgvector(
    query: str,
    top_k: int = 5,
    *,
    subject: str | None = None,
    difficulty: int | None = None,
    session: AsyncSession,
) -> list[dict[str, Any]]:
    """使用 pgvector 进行语义检索。

    Args:
        query: 搜索查询
        top_k: 返回结果数
        subject: 学科过滤
        difficulty: 难度过滤
        session: 数据库会话

    Returns:
        搜索结果列表，按相似度降序
    """
    settings = get_settings()

    # 1. 生成查询向量
    try:
        embedding = await generate_embedding(query)
    except Exception as exc:
        logger.warning("Embedding 生成失败，回退到关键词匹配: %s", exc)
        return await _fallback_keyword_search(query, top_k, subject, difficulty, session)

    # 2. pgvector 余弦距离检索
    embedding_str = f"[{','.join(str(v) for v in embedding)}]"

    where_clauses = []
    params: dict[str, Any] = {
        "embedding": embedding_str,
        "threshold": settings.knowledge_similarity_threshold,
        "top_k": top_k,
    }

    if subject:
        where_clauses.append("kb.subject = :subject")
        params["subject"] = subject
    if difficulty is not None:
        where_clauses.append("kb.difficulty = :difficulty")
        params["difficulty"] = difficulty

    where_sql = ""
    if where_clauses:
        where_sql = "AND " + " AND ".join(where_clauses)

    sql = text(f"""
        SELECT
            kb.id,
            kb.concept,
            kb.content,
            kb.subject,
            kb.difficulty,
            kb.object_types,
            kb.animation_types,
            1.0 - (kb.embedding <=> :embedding::vector) AS similarity
        FROM knowledge_base kb
        WHERE 1.0 - (kb.embedding <=> :embedding::vector) >= :threshold
            {where_sql}
        ORDER BY kb.embedding <=> :embedding::vector
        LIMIT :top_k
    """)

    try:
        result = await session.execute(sql, params)
        rows = result.fetchall()
    except Exception as exc:
        logger.warning("pgvector 检索失败，回退到关键词匹配: %s", exc)
        return await _fallback_keyword_search(query, top_k, subject, difficulty, session)

    return [
        {
            "id": str(row.id) if row.id else row.concept,
            "concept": row.concept,
            "content": row.content[:500] if row.content else "",
            "subject": row.subject,
            "difficulty": row.difficulty or 3,
            "similarity": round(row.similarity, 4) if row.similarity else 0.0,
            "object_types": row.object_types or [],
            "animation_types": row.animation_types or [],
        }
        for row in rows
    ]


async def _fallback_keyword_search(
    query: str,
    top_k: int,
    subject: str | None,
    difficulty: int | None,
    session: AsyncSession,
) -> list[dict[str, Any]]:
    """关键词匹配降级方案。"""
    from sqlalchemy import select

    query_lower = query.lower()

    # 从 DB 查询，用 ILIKE 做模糊匹配
    sql = text("""
        SELECT
            id, concept, content, subject, difficulty,
            object_types, animation_types,
            CASE
                WHEN LOWER(concept) LIKE :exact THEN 0.95
                WHEN LOWER(content) LIKE :partial THEN 0.70
                WHEN LOWER(subject) LIKE :subject_match THEN 0.50
                ELSE 0.10
            END AS similarity
        FROM knowledge_base
        WHERE
            LOWER(concept) LIKE :partial
            OR LOWER(content) LIKE :partial
        ORDER BY similarity DESC
        LIMIT :top_k
    """)

    params = {
        "exact": f"%{query_lower}%",
        "partial": f"%{query_lower}%",
        "subject_match": f"%{query_lower}%",
        "top_k": top_k,
    }

    result = await session.execute(sql, params)
    rows = result.fetchall()

    return [
        {
            "id": str(row.id) if row.id else row.concept,
            "concept": row.concept,
            "content": (row.content or "")[:500],
            "subject": row.subject,
            "difficulty": row.difficulty or 3,
            "similarity": round(row.similarity, 4) if row.similarity else 0.0,
            "object_types": row.object_types or [],
            "animation_types": row.animation_types or [],
        }
        for row in rows
    ]


async def seed_knowledge_embeddings(session: AsyncSession) -> int:
    """从 seed_knowledge.json 生成 embedding 并写入 knowledge_base 表。

    Returns:
        写入的条目数
    """
    seed_path = Path(__file__).resolve().parent.parent / "data" / "seed_knowledge.json"

    if not seed_path.exists():
        logger.warning("种子数据文件不存在: %s", seed_path)
        return 0

    seed_data = json.loads(seed_path.read_text(encoding="utf-8"))
    count = 0

    for item in seed_data:
        concept = item.get("concept", "")
        content = item.get("content", "")

        # 检查是否已存在
        check_sql = text("SELECT id FROM knowledge_base WHERE concept = :concept")
        result = await session.execute(check_sql, {"concept": concept})
        if result.fetchone():
            logger.debug("知识点已存在，跳过: %s", concept)
            continue

        # 生成 embedding
        try:
            embedding = await generate_embedding(f"{concept}: {content}")
        except Exception as exc:
            logger.warning("Embedding 生成失败 [%s]: %s", concept, exc)
            continue

        embedding_str = f"[{','.join(str(v) for v in embedding)}]"

        # 写入
        insert_sql = text("""
            INSERT INTO knowledge_base
                (concept, content, embedding, subject, difficulty, object_types, animation_types)
            VALUES
                (:concept, :content, :embedding::vector, :subject, :difficulty, :object_types, :animation_types)
        """)
        await session.execute(insert_sql, {
            "concept": concept,
            "content": content,
            "embedding": embedding_str,
            "subject": item.get("subject", ""),
            "difficulty": item.get("difficulty", 3),
            "object_types": item.get("object_types", []),
            "animation_types": item.get("animation_types", []),
        })
        count += 1
        logger.info("知识条目已写入: %s (dim=%d)", concept, len(embedding))

    await session.commit()
    logger.info("知识库 embedding 播种完成: %d 条", count)
    return count
