"""Database lookups that enforce ownership of project resources."""

from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .deps import parse_project_id


async def get_owned_project(
    session: AsyncSession,
    project_id: str,
    user_id: uuid.UUID,
    *,
    for_update: bool = False,
):
    """Return a project only when it belongs to ``user_id``.

    A single owner-filtered query deliberately makes a missing project and a
    foreign project produce the same not-found response.
    """
    from db.models import Project

    query = select(Project).where(
        Project.id == parse_project_id(project_id),
        Project.owner_id == user_id,
    )
    if for_update:
        query = query.with_for_update()

    project = (await session.execute(query)).scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project
