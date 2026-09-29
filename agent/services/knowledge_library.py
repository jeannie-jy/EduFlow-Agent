"""Versioned, permission-scoped knowledge indexing and hybrid retrieval."""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from agents.llm_client import generate_embedding
from config import get_settings
from services.provider_credentials import current_embedding_credential

logger = logging.getLogger(__name__)
INDEX_EMBEDDING_MODEL = "text-embedding-v4"
INDEX_EMBEDDING_DIMENSION = 1024


def split_text(content: str, *, max_chars: int = 900, overlap: int = 100) -> list[dict[str, str]]:
    """Split a bounded text stream while retaining headings and stable offsets."""
    if max_chars <= overlap or overlap < 0:
        raise ValueError("max_chars must exceed overlap")
    normalized = "\n".join(line.rstrip() for line in content.splitlines()).strip()
    if not normalized:
        return []
    chunks: list[dict[str, str]] = []
    start = 0
    while start < len(normalized):
        end = min(start + max_chars, len(normalized))
        if end < len(normalized):
            boundary = normalized.rfind("\n", start + max_chars // 2, end)
            if boundary > start:
                end = boundary + 1
        part = normalized[start:end].strip()
        if part:
            chunks.append({"section": "", "locator": f"char:{start}-{end}", "content": part})
        if end == len(normalized):
            break
        start = max(start + 1, end - overlap)
    return chunks


def _vector_literal(values: list[float]) -> str:
    if len(values) != INDEX_EMBEDDING_DIMENSION:
        raise ValueError("knowledge embedding must have 1024 dimensions")
    return "[" + ",".join(str(float(value)) for value in values) + "]"


def _canonical_credential_available() -> bool:
    credential = current_embedding_credential()
    settings = get_settings()
    return (
        credential is not None
        and credential.model == INDEX_EMBEDDING_MODEL
        and settings.knowledge_embedding_model == INDEX_EMBEDDING_MODEL
        and settings.embedding_dimension == INDEX_EMBEDDING_DIMENSION
    )


async def index_source(
    session: AsyncSession,
    *,
    source_key: str,
    scope: str,
    title: str,
    version: str,
    chunks: list[dict[str, str]],
    subject: str | None = None,
    difficulty: int | None = None,
    metadata: dict[str, Any] | None = None,
    owner_id: uuid.UUID | None = None,
    material_id: uuid.UUID | None = None,
    source_url: str | None = None,
    source_type: str | None = None,
    author: str | None = None,
    license_name: str | None = None,
    allow_embedding: bool = False,
    publish: bool = False,
    review_status: str = "pending",
) -> dict[str, Any]:
    """Create one immutable source version; retries of the same content are no-ops.

    A new version never becomes visible until all chunks have been persisted.
    Callers control consent for outbound embedding and commit the transaction.
    """
    if scope not in {"builtin", "teacher", "external"}:
        raise ValueError("invalid knowledge scope")
    if scope == "teacher" and (owner_id is None or material_id is None):
        raise ValueError("teacher knowledge requires an owner and material")
    if not source_key or len(source_key) > 240 or not chunks:
        raise ValueError("source key and nonempty chunks are required")
    if allow_embedding and not _canonical_credential_available():
        raise ValueError("the active embedding model does not match the knowledge index")
    digest = hashlib.sha256(
        json.dumps(chunks, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    row = (await session.execute(
        text("SELECT id, owner_id, scope FROM knowledge_sources WHERE source_key = :source_key"),
        {"source_key": source_key},
    )).mappings().first()
    if row is not None and (row["scope"] != scope or row["owner_id"] != owner_id):
        raise PermissionError("source key belongs to a different knowledge owner")
    source_id = row["id"] if row else uuid.uuid4()
    if row is None:
        await session.execute(text("""
            INSERT INTO knowledge_sources
                (id, source_key, scope, owner_id, material_id, title, subject, difficulty,
                 metadata, source_url, source_type, author, license, status)
            VALUES
                (:id, :source_key, :scope, :owner_id, :material_id, :title, :subject, :difficulty,
                 CAST(:metadata AS jsonb), :source_url, :source_type, :author, :license, 'draft')
        """), {
            "id": source_id, "source_key": source_key, "scope": scope,
            "owner_id": owner_id, "material_id": material_id, "title": title,
            "subject": subject, "difficulty": difficulty,
            "metadata": json.dumps(metadata or {}, ensure_ascii=False),
            "source_url": source_url, "source_type": source_type,
            "author": author, "license": license_name,
        })
    previous = (await session.execute(text("""
        SELECT id, checksum, is_current FROM knowledge_versions
        WHERE source_id = :source_id AND version = :version
    """), {"source_id": source_id, "version": version})).mappings().first()
    if previous is not None:
        if previous["checksum"] != digest:
            raise ValueError("a published version cannot be overwritten")
        if not allow_embedding:
            if publish and not previous["is_current"]:
                await publish_version(session, source_id=source_id, version_id=previous["id"])
            return {"source_id": str(source_id), "version_id": str(previous["id"]), "indexed": False}
    vectors: list[str | None] = []
    if allow_embedding:
        for chunk in chunks:
            vectors.append(_vector_literal(await generate_embedding(f"{title}: {chunk['content']}")))
    else:
        vectors = [None] * len(chunks)
    if previous is not None:
        if allow_embedding:
            for ordinal, vector in enumerate(vectors):
                await session.execute(text("""
                    UPDATE knowledge_chunks SET embedding = CAST(:embedding AS vector)
                    WHERE version_id = :version_id AND ordinal = :ordinal AND embedding IS NULL
                """), {"embedding": vector, "version_id": previous["id"], "ordinal": ordinal})
            await session.execute(text("""
                UPDATE knowledge_versions SET embedding_model = :model, indexed_at = :indexed_at
                WHERE id = :version_id
            """), {"model": get_settings().knowledge_embedding_model,
                   "indexed_at": datetime.now(UTC), "version_id": previous["id"]})
        if publish and not previous["is_current"]:
            await publish_version(session, source_id=source_id, version_id=previous["id"])
        return {"source_id": str(source_id), "version_id": str(previous["id"]), "indexed": False}

    version_id = uuid.uuid4()
    await session.execute(text("""
        INSERT INTO knowledge_versions
            (id, source_id, version, checksum, embedding_model, is_current, review_status, indexed_at)
        VALUES
            (:id, :source_id, :version, :checksum, :model, false, :review_status, :indexed_at)
    """), {
        "id": version_id, "source_id": source_id, "version": version,
        "checksum": digest, "model": get_settings().knowledge_embedding_model if allow_embedding else None,
        "review_status": review_status, "indexed_at": datetime.now(UTC),
    })
    for ordinal, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
        await session.execute(text("""
            INSERT INTO knowledge_chunks
                (id, version_id, ordinal, section, locator, content, embedding)
            VALUES
                (:id, :version_id, :ordinal, :section, :locator, :content, CAST(:embedding AS vector))
        """), {
            "id": uuid.uuid4(), "version_id": version_id, "ordinal": ordinal,
            "section": chunk.get("section", "")[:500],
            "locator": chunk.get("locator", "")[:100],
            "content": chunk["content"], "embedding": vector,
        })
    if publish:
        await publish_version(session, source_id=source_id, version_id=version_id)
    return {"source_id": str(source_id), "version_id": str(version_id), "indexed": True}


async def publish_version(
    session: AsyncSession, *, source_id: uuid.UUID, version_id: uuid.UUID
) -> None:
    """Atomically replace a current version after editorial or owner approval."""
    review = (await session.execute(text("""
        SELECT s.scope, v.review_status FROM knowledge_versions v
        JOIN knowledge_sources s ON s.id = v.source_id
        WHERE v.id = :version_id AND s.id = :source_id
    """), {"source_id": source_id, "version_id": version_id})).mappings().first()
    if review is None:
        raise ValueError("knowledge version not found")
    if review["scope"] != "teacher" and review["review_status"] not in {"approved", "legacy"}:
        raise PermissionError("editorial approval required before publishing")
    await session.execute(text("""
        UPDATE knowledge_versions SET is_current = false
        WHERE source_id = :source_id AND is_current
    """), {"source_id": source_id})
    result = await session.execute(text("""
        UPDATE knowledge_versions
        SET is_current = true, published_at = :published_at
        WHERE id = :version_id AND source_id = :source_id
    """), {"source_id": source_id, "version_id": version_id, "published_at": datetime.now(UTC)})
    if result.rowcount != 1:
        raise ValueError("knowledge version not found")
    await session.execute(text("""
        UPDATE knowledge_sources SET status = 'published', updated_at = :updated_at
        WHERE id = :source_id
    """), {"source_id": source_id, "updated_at": datetime.now(UTC)})


async def search_library(
    session: AsyncSession,
    query: str,
    *,
    top_k: int = 5,
    project_id: uuid.UUID | None = None,
    owner_id: uuid.UUID | None = None,
    subject: str | None = None,
    difficulty: int | None = None,
    scope_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Fuse scoped vector and trigram candidates without post-filtering secrets."""
    if not query.strip():
        return []
    if project_id is not None and owner_id is None:
        raise PermissionError("project knowledge search requires an owner")
    if scope_filter not in (None, "teacher"):
        raise ValueError("unsupported knowledge scope filter")
    if scope_filter == "teacher" and (project_id is None or owner_id is None):
        raise PermissionError("teacher-only search requires an owned project")
    visible = """(
        s.scope IN ('builtin', 'external') OR
        (s.scope = 'teacher' AND s.owner_id = :owner_id AND EXISTS (
            SELECT 1 FROM project_knowledge_sources pks
            JOIN projects p ON p.id = pks.project_id AND p.owner_id = :owner_text
            WHERE pks.project_id = :project_id AND pks.source_id = s.id
        ))
    )"""
    filters = ["s.status = 'published'", "v.is_current", visible]
    if scope_filter == "teacher":
        filters.append("s.scope = 'teacher'")
    params: dict[str, Any] = {
        "query": query.strip()[:500], "limit": min(max(top_k * 4, 5), 40),
        "owner_id": owner_id, "project_id": project_id,
        "owner_text": str(owner_id) if owner_id else None,
    }
    if subject:
        filters.append("s.subject = :subject")
        params["subject"] = subject
    if difficulty is not None:
        filters.append("s.difficulty = :difficulty")
        params["difficulty"] = difficulty
    base = """
        FROM knowledge_chunks c
        JOIN knowledge_versions v ON v.id = c.version_id
        JOIN knowledge_sources s ON s.id = v.source_id
    """
    columns = """
        SELECT s.source_key, s.title, s.scope, s.source_url, s.source_type,
               s.author, s.license, s.metadata,
               s.subject, s.difficulty, v.version, c.id AS chunk_id,
               c.ordinal, c.section, c.locator, c.content,
    """
    candidates: dict[str, dict[str, Any]] = {}

    async def add_rows(sql: str, bind: dict[str, Any], channel: str) -> None:
        rows = (await session.execute(text(sql), bind)).mappings().all()
        for rank, row in enumerate(rows, 1):
            key = str(row["chunk_id"])
            entry = candidates.setdefault(key, dict(row))
            entry["score"] = max(float(entry["score"]), float(row["score"]))
            entry["rrf_score"] = entry.get("rrf_score", 0.0) + 1 / (60 + rank)
            entry.setdefault("matched_by", []).append(channel)

    from services.knowledge_service import _lexical_search_terms

    terms = _lexical_search_terms(query)[:12]
    lexical_clauses = []
    for index, term in enumerate(terms):
        params[f"term_{index}"] = f"%{term}%"
        lexical_clauses.append(f"(c.content ILIKE :term_{index} OR s.title ILIKE :term_{index})")
    lexical_sql = (
        columns + "GREATEST(similarity(c.content, :query), similarity(s.title, :query)) AS score "
        + base + " WHERE " + " AND ".join(filters)
        + (" AND (" + " OR ".join(lexical_clauses) + ") " if lexical_clauses else " AND false ")
        + "ORDER BY score DESC LIMIT :limit"
    )
    await add_rows(lexical_sql, params, "keyword")

    if _canonical_credential_available():
        try:
            vector = _vector_literal(await generate_embedding(params["query"]))
            vector_sql = (
                columns + "1 - (c.embedding <=> CAST(:embedding AS vector)) AS score "
                + base + " WHERE " + " AND ".join(filters)
                + " AND c.embedding IS NOT NULL AND v.embedding_model = :model "
                + "AND 1 - (c.embedding <=> CAST(:embedding AS vector)) >= :threshold "
                + "ORDER BY c.embedding <=> CAST(:embedding AS vector) LIMIT :limit"
            )
            async with session.begin_nested():
                await add_rows(vector_sql, {
                    **params, "embedding": vector, "model": get_settings().knowledge_embedding_model,
                    "threshold": get_settings().knowledge_similarity_threshold,
                }, "semantic")
        except Exception as exc:
            logger.warning("semantic knowledge search failed; keyword evidence retained: %s", exc)

    def local_score(row: dict[str, Any]) -> float:
        """Cheap deterministic rerank; never asks a paid model."""
        title = str(row["title"]).casefold()
        content = str(row["content"]).casefold()
        query_lower = params["query"].casefold()
        exact_title = 0.04 if title and title in query_lower else 0.0
        anchor_hits = sum(term.casefold() in title for term in terms[:8])
        content_hits = sum(term.casefold() in content for term in terms[:8])
        return row["rrf_score"] + exact_title + min(anchor_hits, 3) * 0.006 + min(content_hits, 3) * 0.001

    ranked = sorted(candidates.values(), key=local_score, reverse=True)
    return [{
        "id": str(row["chunk_id"]), "chunk_id": str(row["chunk_id"]),
        "source_id": row["source_key"], "source_key": row["source_key"],
        "title": row["title"], "concept": row["title"],
        "content": row["content"][:1000], "subject": row["subject"],
        "difficulty": row["difficulty"], "similarity": float(row["score"]),
        "rrf_score": round(row["rrf_score"], 6),
        "local_score": round(local_score(row), 6),
        "matched_by": row["matched_by"], "scope": row["scope"],
        "version": row["version"], "section": row["section"],
        "locator": row["locator"], "source_url": row["source_url"],
        "author": row["author"], "license": row["license"],
        "source_type": row["source_type"], "metadata": row["metadata"],
        "trust": "retrieved_untrusted",
    } for row in ranked[:top_k]]
