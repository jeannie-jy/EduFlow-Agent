"""Purge due account deletions, including object-store data, after the cooling period."""

from __future__ import annotations

import asyncio


async def process_due_deletions() -> int:
    from db.database import close_database
    from services.account_deletion import process_due_deletions as process
    try:
        return await process()
    finally:
        await close_database()


if __name__ == "__main__":
    print(asyncio.run(process_due_deletions()))
