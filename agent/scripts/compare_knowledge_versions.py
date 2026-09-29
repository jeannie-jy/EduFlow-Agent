"""Compare legacy and v2 retrieval on a migrated test database before read cutover."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from db.database import async_session_factory
from evals.graders.retrieval import grade_retrieval
from evals.models import load_cases
from services.knowledge_library import search_library
from services.knowledge_service import search_knowledge_pgvector


async def compare(dataset: Path) -> dict:
    cases = load_cases(dataset)
    results = []
    async with async_session_factory() as session:
        for case in cases:
            if case.retrieval is None:
                continue
            top_k = case.retrieval.k
            old = await search_knowledge_pgvector(case.topic, top_k=top_k, session=session)
            new = await search_library(session, case.topic, top_k=top_k)
            old_ids = [str(row.get("source_key") or row.get("id")) for row in old]
            new_ids = [str(row["source_key"]) for row in new]
            results.append({
                "case_id": case.case_id,
                "old_ids": old_ids,
                "new_ids": new_ids,
                "old_metrics": grade_retrieval(case, old_ids),
                "new_metrics": grade_retrieval(case, new_ids),
                "overlap_at_k": len(set(old_ids) & set(new_ids)),
            })
    evaluable = [row for row in results if not next(
        case.retrieval.must_abstain_without_evidence for case in cases if case.case_id == row["case_id"]
    )]
    def recall(rows: list[dict], field: str) -> float | None:
        return round(sum(row[field]["recall_at_k"] for row in rows) / len(rows), 4) if rows else None
    return {
        "case_count": len(results),
        "legacy_recall_at_k": recall(evaluable, "old_metrics"),
        "v2_recall_at_k": recall(evaluable, "new_metrics"),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = asyncio.run(compare(args.dataset))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "results"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
