"""Strict administrator APIs for user roles and session revocation."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, model_validator
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_session
from db.models import AuthSession, User
from services.audit import record_audit

from .auth import require_admin

router = APIRouter(prefix="/admin", tags=["admin"])


class AdminUserUpdate(BaseModel):
    role: Literal["student", "teacher", "admin"] | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> AdminUserUpdate:
        if self.role is None and self.is_active is None:
            raise ValueError("At least one of role or is_active is required")
        return self


def _public_user(user: User, session_count: int = 0) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "email": user.email,
        "nickname": user.nickname,
        "role": user.role,
        "is_active": user.is_active,
        "session_count": session_count,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


async def _target_user(session: AsyncSession, user_id: uuid.UUID) -> User:
    target = await session.scalar(
        select(User).where(User.id == user_id).with_for_update()
    )
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    return target


@router.get("/users")
async def list_users(
    session: AsyncSession = Depends(get_session),
    _admin: Annotated[User, Depends(require_admin)] = None,
    cursor: uuid.UUID | None = Query(default=None),
    role: Literal["student", "teacher", "admin"] | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1, max_length=100),
    limit: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    """List users newest-first using an opaque user-id cursor."""
    predicates = []
    if role is not None:
        predicates.append(User.role == role)
    if is_active is not None:
        predicates.append(User.is_active.is_(is_active))
    if search is not None:
        term = f"%{search.strip().lower()}%"
        predicates.append(
            or_(func.lower(User.email).like(term), func.lower(User.nickname).like(term))
        )
    if cursor is not None:
        cursor_exists = await session.scalar(select(User.id).where(User.id == cursor))
        if cursor_exists is None:
            raise HTTPException(status_code=422, detail="Invalid user cursor")
        cursor_created_at = (
            select(User.created_at).where(User.id == cursor).scalar_subquery()
        )
        predicates.append(
            or_(
                User.created_at < cursor_created_at,
                and_(User.created_at == cursor_created_at, User.id < cursor),
            )
        )

    query = select(User)
    if predicates:
        query = query.where(*predicates)
    result = await session.execute(
        query.order_by(User.created_at.desc(), User.id.desc()).limit(limit + 1)
    )
    rows = list(result.scalars().all())
    has_more = len(rows) > limit
    users = rows[:limit]

    counts: dict[uuid.UUID, int] = {}
    if users:
        count_result = await session.execute(
            select(AuthSession.user_id, func.count(AuthSession.id))
            .where(
                AuthSession.user_id.in_([user.id for user in users]),
                AuthSession.expires_at > datetime.now(timezone.utc),
            )
            .group_by(AuthSession.user_id)
        )
        counts = {user_id: int(count) for user_id, count in count_result.all()}

    return {
        "users": [_public_user(user, counts.get(user.id, 0)) for user in users],
        "next_cursor": str(users[-1].id) if has_more and users else None,
    }


@router.patch("/users/{user_id}")
async def update_user(
    user_id: uuid.UUID,
    body: AdminUserUpdate,
    session: AsyncSession = Depends(get_session),
    admin: Annotated[User, Depends(require_admin)] = None,
) -> dict[str, Any]:
    """Change role/active state while preserving an active administrator."""
    target = await _target_user(session, user_id)
    new_role = body.role if body.role is not None else target.role
    new_active = body.is_active if body.is_active is not None else target.is_active

    removes_own_admin_access = target.id == admin.id and (
        new_role != "admin" or not new_active
    )
    if removes_own_admin_access:
        raise HTTPException(status_code=409, detail="Administrators cannot remove their own access")

    removes_active_admin = target.role == "admin" and target.is_active and (
        new_role != "admin" or not new_active
    )
    if removes_active_admin:
        active_admins = list(
            (
                await session.execute(
                    select(User)
                    .where(User.role == "admin", User.is_active.is_(True))
                    .with_for_update()
                )
            ).scalars().all()
        )
        if len(active_admins) <= 1:
            raise HTTPException(status_code=409, detail="Cannot remove the last active administrator")

    previous = {"role": target.role, "is_active": target.is_active}
    changed = previous != {"role": new_role, "is_active": new_active}
    target.role = new_role
    target.is_active = new_active
    revoked = 0
    if changed:
        result = await session.execute(
            delete(AuthSession).where(AuthSession.user_id == target.id)
        )
        revoked = int(result.rowcount or 0)
        record_audit(
            session,
            action="admin.user.update",
            resource_type="user",
            resource_id=str(target.id),
            actor_id=admin.id,
            details={
                "before": previous,
                "after": {"role": new_role, "is_active": new_active},
                "sessions_revoked": revoked,
            },
        )
    await session.flush()
    return _public_user(target, 0 if changed else await _session_count(session, target.id))


async def _session_count(session: AsyncSession, user_id: uuid.UUID) -> int:
    return int(
        await session.scalar(
            select(func.count(AuthSession.id)).where(
                AuthSession.user_id == user_id,
                AuthSession.expires_at > datetime.now(timezone.utc),
            )
        )
        or 0
    )


@router.delete("/users/{user_id}/sessions")
async def revoke_user_sessions(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    admin: Annotated[User, Depends(require_admin)] = None,
) -> dict[str, int]:
    """Revoke every opaque login session belonging to one user."""
    target = await _target_user(session, user_id)
    result = await session.execute(
        delete(AuthSession).where(AuthSession.user_id == target.id)
    )
    revoked = int(result.rowcount or 0)
    record_audit(
        session,
        action="admin.sessions.revoke",
        resource_type="user",
        resource_id=str(target.id),
        actor_id=admin.id,
        details={"sessions_revoked": revoked},
    )
    return {"revoked": revoked}
