"""Import the existing vetted-for-compatibility seed into the versioned index.

The 22 legacy entries remain labelled ``legacy`` until an editor reviews them.
This script never claims that additional automatically generated entries were
human reviewed. Run after ``alembic upgrade head``.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from db.database import async_session_factory
from evals.evaluation_credentials import online_eval_credential_scope
from services.knowledge_library import _canonical_credential_available, index_source
from services.knowledge_service import stable_source_key


async def main() -> int:
    data_path = Path(__file__).resolve().parents[1] / "data" / "seed_knowledge.json"
    entries = json.loads(data_path.read_text(encoding="utf-8"))
    imported = 0
    with online_eval_credential_scope():
        async with async_session_factory() as session:
            for item in entries:
                concept = item["concept"]
                await index_source(
                    session,
                    source_key=item.get("source_key") or stable_source_key(concept, item.get("subject")),
                    scope="builtin",
                    title=concept,
                    version="legacy-1",
                    chunks=[{"section": concept, "locator": "concept:1", "content": item["content"]}],
                    subject=item.get("subject"),
                    difficulty=item.get("difficulty"),
                    metadata={
                        "definition": item["content"],
                        "steps": [], "pitfalls": [], "prerequisites": [],
                        "object_types": item.get("object_types", []),
                        "animation_types": item.get("animation_types", []),
                    },
                    source_type="legacy_seed",
                    allow_embedding=_canonical_credential_available(),
                    publish=True,
                    review_status="legacy",
                )
                imported += 1
            await session.commit()
    return imported


if __name__ == "__main__":
    print(f"Imported {asyncio.run(main())} legacy knowledge items")
