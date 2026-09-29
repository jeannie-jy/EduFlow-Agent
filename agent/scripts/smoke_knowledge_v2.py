"""Read-only lexical smoke check of a migrated PostgreSQL v2 knowledge index.

Requires DATABASE_URL pointing at an isolated test database. No embeddings,
generation calls, imports, or changes to database rows are performed.
"""

from __future__ import annotations

import asyncio
import json

from db.database import async_session_factory
from services.knowledge_library import search_library


async def main() -> int:
    async with async_session_factory() as session:
        known = await search_library(session, "二分查找", top_k=5)
        unknown = await search_library(session, "zzzxqv_missing_topic_928341", top_k=5)
    ids = [row["source_key"] for row in known]
    report = {
        "known_query": "二分查找",
        "known_source_keys": ids,
        "expected_source_found": "algo_binary_search" in ids,
        "unknown_source_keys": [row["source_key"] for row in unknown],
        "unknown_abstained": not unknown,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["expected_source_found"] and report["unknown_abstained"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
