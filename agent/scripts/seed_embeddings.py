#!/usr/bin/env python3
"""知识库种子数据 embedding 生成脚本。

用法:
    cd agent
    python -m scripts.seed_embeddings

从 data/seed_knowledge.json 读取 22 个知识点，
为每个知识点生成 text-embedding-3-small 向量，
写入 PostgreSQL knowledge_base 表。
"""

from __future__ import annotations

import asyncio
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("seed-embeddings")


async def main() -> None:
    """主入口。"""
    from db.database import async_session_factory
    from services.knowledge_service import seed_knowledge_embeddings

    logger.info("开始播种知识库 embedding...")

    try:
        async with async_session_factory() as session:
            count = await seed_knowledge_embeddings(session)
        logger.info("播种完成: 写入 %d 条，跳过已存在的条目", count)
    except Exception as exc:
        logger.error("播种失败: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
