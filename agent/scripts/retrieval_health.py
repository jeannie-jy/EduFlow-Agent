#!/usr/bin/env python3
"""Fail-fast retrieval health check for online CI.

The check deliberately exercises the same retrieval boundary used by the
production workflow after the knowledge-base embeddings have been seeded.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys

from services.retrieval import retrieve_knowledge_context

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("retrieval-health")


async def main() -> int:
    result = await retrieve_knowledge_context("Dijkstra最短路径算法")
    summary = {
        "status": result.get("status"),
        "candidate_count": int(result.get("candidate_count", 0) or 0),
        "selected_count": int(result.get("selected_count", 0) or 0),
    }
    print(json.dumps(summary, ensure_ascii=False))
    if summary["candidate_count"] <= 0:
        logger.error("retrieval health check failed: candidate_count must be > 0")
        return 1
    logger.info("retrieval health check passed: candidate_count=%d", summary["candidate_count"])
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except Exception as exc:
        logger.error("retrieval health check failed: %s", exc)
        sys.exit(1)
