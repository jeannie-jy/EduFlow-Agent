"""知识库服务 — pgvector 向量检索。

提供:
- 从 seed_knowledge.json 生成 embedding 并写入 knowledge_base 表
- 语义搜索（pgvector 余弦距离）
- 降级：pgvector 不可用时回退到关键词匹配
"""

from __future__ import annotations

import json
import logging
import hashlib
import re
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from agents.llm_client import EmbeddingDimensionError, generate_embedding
from config import get_settings

logger = logging.getLogger(__name__)


# Stable public identifiers are used for citations and evaluation. The UUID
# primary key remains an internal database identity and is never exposed as a
# benchmark gold label.
_SOURCE_KEY_BY_CONCEPT = {
    "冒泡排序": "algo_bubble_sort",
    "快速排序": "algo_quick_sort",
    "归并排序": "algo_merge_sort",
    "二分查找": "algo_binary_search",
    "递归": "algo_recursion",
    "Dijkstra最短路径算法": "algo-dijkstra-constraints",
    "BFS与DFS": "algo_graph_traversal",
    "动态规划": "algo_dynamic_programming",
    "最小生成树": "algo_minimum_spanning_tree",
    "哈希表": "ds_hash_table",
    "二叉树与AVL树": "ds-avl-rotations",
    "栈与队列": "ds_stack_queue",
    "红黑树插入": "ds_red_black_tree",
    "进程调度": "os_process_scheduling",
    "同步与互斥": "os_sync_mutex",
    "死锁": "os-deadlock-conditions",
    "分页与虚拟内存": "os_virtual_memory",
    "TCP三次握手": "net-tcp-rfc-summary",
    "HTTP协议": "net_http",
    "数据库索引与B+树": "db-bplus-tree",
    "数据库事务与隔离级别": "db-mvcc-visibility",
    "设计模式": "se-solid-dip",
}

# Generic query words should not turn an unknown-topic request into a false
# positive lexical hit. The fallback still requires a meaningful two-to-four
# character anchor (for example ``依赖``/``倒置``) present in the corpus.
_LEXICAL_STOPWORDS = {
    "仅", "根据", "知识库", "解释", "未收录", "收录", "私有", "算法", "为什么", "要求", "如何",
    "说明", "含义", "中的", "以及", "进行", "一个", "原则", "问题", "方法", "数据",
    "结构", "相关", "请问", "介绍", "能够", "知识", "私有算法", "的", "在",
}


def _lexical_search_terms(query: str) -> list[str]:
    """Extract bounded, meaningful lexical anchors for hybrid retrieval."""
    normalized = query.lower()
    for stopword in sorted(_LEXICAL_STOPWORDS, key=len, reverse=True):
        normalized = normalized.replace(stopword, " ")
    terms: set[str] = set()
    for span in re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+", normalized):
        if span in _LEXICAL_STOPWORDS:
            continue
        if len(span) <= 8:
            terms.add(span)
            continue
        # Chinese has no whitespace tokenization. Small n-grams catch a
        # documented phrase such as ``依赖倒置`` without matching a whole
        # natural-language question verbatim.
        for size in (2, 3, 4):
            terms.update(
                span[index : index + size]
                for index in range(len(span) - size + 1)
                if span[index : index + size] not in _LEXICAL_STOPWORDS
            )
    eligible = [
        term for term in terms
        if len(term) >= 2 and not term.isdigit() and not (term.isascii() and len(term) < 3)
    ]
    # Keep both phrase-level anchors and short Chinese bigrams. Capping only
    # by length can discard the exact ``依赖``/``倒置`` anchors while retaining
    # longer question fragments that do not occur in the document.
    long_terms = sorted((term for term in eligible if len(term) >= 3), key=lambda item: (-len(item), item))[:12]
    short_terms = sorted((term for term in eligible if len(term) == 2))[:12]
    return long_terms + short_terms


def stable_source_key(concept: str, subject: str | None = None) -> str:
    """Return a deterministic, readable identifier for a knowledge item."""
    known = _SOURCE_KEY_BY_CONCEPT.get(concept)
    if known:
        return known
    prefix = (subject or "knowledge").strip().lower().replace(" ", "_")
    digest = hashlib.sha256(concept.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


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
    except EmbeddingDimensionError:
        # A schema/provider mismatch must not be hidden by keyword fallback;
        # otherwise the application appears healthy while RAG silently loses
        # semantic retrieval.
        raise
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
            kb.source_key,
            kb.concept,
            kb.content,
            kb.subject,
            kb.difficulty,
            kb.object_types,
            kb.animation_types,
            1.0 - (kb.embedding <=> CAST(:embedding AS vector)) AS similarity
        FROM knowledge_base kb
        WHERE 1.0 - (kb.embedding <=> CAST(:embedding AS vector)) >= :threshold
            {where_sql}
        ORDER BY kb.embedding <=> CAST(:embedding AS vector)
        LIMIT :top_k
    """)

    try:
        result = await session.execute(sql, params)
        rows = result.fetchall()
    except Exception as exc:
        logger.warning("pgvector 检索失败，回退到关键词匹配: %s", exc)
        # asyncpg marks the current transaction as failed after a SQL error.
        # Roll it back before issuing the fallback query; otherwise PostgreSQL
        # rejects every subsequent statement with InFailedSQLTransactionError.
        await session.rollback()
        return await _fallback_keyword_search(query, top_k, subject, difficulty, session)

    # A valid document can sit below the semantic threshold for a short or
    # paraphrased query. Use a bounded lexical pass before declaring that the
    # knowledge base has no evidence; unlike lowering the global threshold,
    # this only activates when vector retrieval produced no candidates.
    if not rows:
        return await _fallback_keyword_search(query, top_k, subject, difficulty, session)

    return [
        {
            "id": str(row.id) if row.id else row.concept,
            "source_key": row.source_key,
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
    query_lower = query.lower()
    terms = _lexical_search_terms(query_lower)
    if not terms:
        return []

    term_params = {f"term_{index}": f"%{term}%" for index, term in enumerate(terms)}
    term_clauses = [
        f"(LOWER(concept) LIKE :term_{index} OR LOWER(content) LIKE :term_{index})"
        for index in range(len(terms))
    ]
    term_score = " + ".join(
        f"CASE WHEN LOWER(concept) LIKE :term_{index} OR LOWER(content) LIKE :term_{index} THEN 1 ELSE 0 END"
        for index in range(len(terms))
    )
    sql = text(f"""
        SELECT
            id, source_key, concept, content, subject, difficulty,
            object_types, animation_types,
            (0.70 + LEAST(({term_score}) * 0.05, 0.25)) AS similarity
        FROM knowledge_base
        WHERE
            {' OR '.join(term_clauses)}
        ORDER BY similarity DESC
        LIMIT :top_k
    """)

    params = {**term_params, "top_k": top_k}

    result = await session.execute(sql, params)
    rows = result.fetchall()

    return [
        {
            "id": str(row.id) if row.id else row.concept,
            "source_key": row.source_key,
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
        source_key = item.get("source_key") or stable_source_key(
            concept, item.get("subject")
        )

        # 检查是否已存在
        check_sql = text(
            "SELECT id, source_key, embedding IS NOT NULL AS has_embedding "
            "FROM knowledge_base WHERE concept = :concept"
        )
        result = await session.execute(check_sql, {"concept": concept})
        existing = result.fetchone()

        # 生成 embedding
        try:
            embedding = await generate_embedding(f"{concept}: {content}")
        except Exception as exc:
            logger.warning("Embedding 生成失败 [%s]: %s", concept, exc)
            continue

        embedding_str = f"[{','.join(str(v) for v in embedding)}]"

        # Write new rows, or repair rows whose content survived a vector
        # dimension migration but whose embedding was intentionally cleared.
        if existing and not existing.has_embedding:
            update_sql = text("""
                UPDATE knowledge_base
                SET content = :content,
                    source_key = :source_key,
                    subject = :subject,
                    difficulty = :difficulty,
                    object_types = :object_types,
                    animation_types = :animation_types,
                    embedding = CAST(:embedding AS vector)
                WHERE id = :id
            """)
            await session.execute(update_sql, {
                "id": existing.id,
                "source_key": source_key,
                "content": content,
                "embedding": embedding_str,
                "subject": item.get("subject", ""),
                "difficulty": item.get("difficulty", 3),
                "object_types": item.get("object_types", []),
                "animation_types": item.get("animation_types", []),
            })
            count += 1
            logger.info("知识条目 embedding 已更新: %s", concept)
            continue
        if existing:
            if existing.source_key != source_key:
                await session.execute(
                    text("UPDATE knowledge_base SET source_key = :source_key WHERE id = :id"),
                    {"id": existing.id, "source_key": source_key},
                )
                logger.info("知识条目 source_key 已更新: %s -> %s", concept, source_key)
            logger.debug("知识点已存在且已有 embedding，跳过: %s", concept)
            continue

        insert_sql = text("""
            INSERT INTO knowledge_base
                (source_key, concept, content, embedding, subject, difficulty, object_types, animation_types)
            VALUES
                (:source_key, :concept, :content, CAST(:embedding AS vector), :subject, :difficulty, :object_types, :animation_types)
        """)
        await session.execute(insert_sql, {
            "source_key": source_key,
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
