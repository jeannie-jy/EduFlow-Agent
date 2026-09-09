"""Promote the first administrator without creating a second control plane.

This command is intentionally bootstrap-only: once an active administrator
exists, all later role changes must use the authenticated admin API.
"""

from __future__ import annotations

import argparse
import asyncio
import json

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import async_session_factory, close_database
from db.models import AuthSession, User
from services.audit import record_audit


async def bootstrap_admin(session: AsyncSession, email: str) -> dict[str, object]:
    normalized = email.strip().lower()
    target = await session.scalar(
        select(User).where(func.lower(User.email) == normalized).with_for_update()
    )
    if target is None:
        raise ValueError("User not found; register the account before bootstrapping")

    active_admins = list(
        (
            await session.execute(
                select(User)
                .where(User.role == "admin", User.is_active.is_(True))
                .with_for_update()
            )
        ).scalars().all()
    )
    if active_admins:
        if target.role == "admin" and target.is_active:
            return {"user_id": str(target.id), "email": target.email, "changed": False}
        raise RuntimeError(
            "An active administrator already exists; use the admin API for role changes"
        )

    before = {"role": target.role, "is_active": target.is_active}
    target.role = "admin"
    target.is_active = True
    result = await session.execute(
        delete(AuthSession).where(AuthSession.user_id == target.id)
    )
    record_audit(
        session,
        action="admin.bootstrap",
        resource_type="user",
        resource_id=str(target.id),
        actor_id=target.id,
        details={
            "before": before,
            "after": {"role": "admin", "is_active": True},
            "sessions_revoked": int(result.rowcount or 0),
        },
    )
    await session.flush()
    return {"user_id": str(target.id), "email": target.email, "changed": True}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="existing account email")
    return parser.parse_args()


async def async_main() -> int:
    try:
        args = parse_args()
        async with async_session_factory() as session:
            try:
                result = await bootstrap_admin(session, args.email)
                await session.commit()
            except Exception:
                await session.rollback()
                raise
        print(json.dumps(result, ensure_ascii=False))
        return 0
    finally:
        await close_database()


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
