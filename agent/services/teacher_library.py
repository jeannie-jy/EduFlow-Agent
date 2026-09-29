"""Owner-scoped teacher materials and project authorization links."""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def teacher_source_key(material_id: uuid.UUID) -> str:
    return f"teacher-{material_id}"


async def enable_library_material(
    session: AsyncSession, *, material_id: uuid.UUID, owner_id: uuid.UUID
) -> dict[str, str]:
    """Keep an owned material until deletion and create its unpublished source shell."""
    material = (await session.execute(text("""
        UPDATE materials SET is_library = true, expires_at = NULL
        WHERE id = :material_id AND owner_id = :owner_id
        RETURNING id, original_filename
    """), {"material_id": material_id, "owner_id": owner_id})).mappings().first()
    if material is None:
        raise LookupError("material not found")
    key = teacher_source_key(material_id)
    await session.execute(text("""
        INSERT INTO knowledge_sources
            (id, source_key, scope, owner_id, material_id, title, source_type, status)
        VALUES
            (:id, :source_key, 'teacher', :owner_id, :material_id, :title,
             'teacher_material', 'draft')
        ON CONFLICT (source_key) DO NOTHING
    """), {
        "id": uuid.uuid4(), "source_key": key, "owner_id": owner_id,
        "material_id": material_id, "title": material["original_filename"],
    })
    source = (await session.execute(text("""
        SELECT id, scope, owner_id, material_id FROM knowledge_sources
        WHERE source_key = :source_key
    """), {"source_key": key})).mappings().first()
    if (
        source is None or source["scope"] != "teacher"
        or source["owner_id"] != owner_id or source["material_id"] != material_id
    ):
        raise PermissionError("teacher source key conflict")
    return {"material_id": str(material_id), "source_id": str(source["id"])}


async def attach_material_to_project(
    session: AsyncSession, *, project_id: uuid.UUID, material_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> uuid.UUID:
    """Authorize both ownerships inside the INSERT query, never after retrieval."""
    params = {
        "project_id": project_id, "material_id": material_id,
        "owner_id": owner_id, "owner_text": str(owner_id),
    }
    await session.execute(text("""
        INSERT INTO project_knowledge_sources (project_id, source_id)
        SELECT p.id, s.id
        FROM projects p
        JOIN materials m ON m.id = :material_id AND m.owner_id = :owner_id
        JOIN knowledge_sources s ON s.material_id = m.id
            AND s.owner_id = :owner_id AND s.scope = 'teacher'
        WHERE p.id = :project_id AND p.owner_id = :owner_text AND m.is_library
        ON CONFLICT (project_id, source_id) DO NOTHING
    """), params)
    link = (await session.execute(text("""
        SELECT s.id AS source_id FROM project_knowledge_sources pks
        JOIN projects p ON p.id = pks.project_id AND p.owner_id = :owner_text
        JOIN knowledge_sources s ON s.id = pks.source_id
            AND s.owner_id = :owner_id AND s.scope = 'teacher'
        JOIN materials m ON m.id = s.material_id
            AND m.owner_id = :owner_id AND m.is_library
        WHERE pks.project_id = :project_id AND m.id = :material_id
    """), params)).mappings().first()
    if link is None:
        raise LookupError("project or library material not found")
    return link["source_id"]


async def list_project_materials(
    session: AsyncSession, *, project_id: uuid.UUID, owner_id: uuid.UUID
) -> list[dict[str, str]]:
    """Return only sources authorized for an owned project."""
    params = {"project_id": project_id, "owner_id": owner_id, "owner_text": str(owner_id)}
    exists = (await session.execute(text("""
        SELECT 1 FROM projects WHERE id = :project_id AND owner_id = :owner_text
    """), params)).scalar_one_or_none()
    if exists is None:
        raise LookupError("project not found")
    rows = (await session.execute(text("""
        SELECT m.id AS material_id, m.original_filename AS filename,
               s.id AS source_id, s.status AS index_status
        FROM project_knowledge_sources pks
        JOIN projects p ON p.id = pks.project_id AND p.owner_id = :owner_text
        JOIN knowledge_sources s ON s.id = pks.source_id
            AND s.owner_id = :owner_id AND s.scope = 'teacher'
        JOIN materials m ON m.id = s.material_id
            AND m.owner_id = :owner_id AND m.is_library
        WHERE pks.project_id = :project_id
        ORDER BY m.original_filename, m.id
    """), params)).mappings().all()
    return [
        {
            "material_id": str(row["material_id"]), "filename": row["filename"],
            "source_id": str(row["source_id"]), "index_status": row["index_status"],
        }
        for row in rows
    ]


async def detach_material_from_project(
    session: AsyncSession, *, project_id: uuid.UUID, material_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> None:
    """Unlink only an owned project and owned material; repeated removal is safe."""
    await session.execute(text("""
        DELETE FROM project_knowledge_sources pks
        USING projects p, materials m, knowledge_sources s
        WHERE pks.project_id = p.id AND pks.source_id = s.id
          AND s.material_id = m.id AND s.scope = 'teacher'
          AND p.id = :project_id AND p.owner_id = :owner_text
          AND m.id = :material_id AND m.owner_id = :owner_id
          AND s.owner_id = :owner_id
    """), {
        "project_id": project_id, "material_id": material_id,
        "owner_id": owner_id, "owner_text": str(owner_id),
    })
