"""Bootstrap official URL proposals as unpublished review candidates.

Run only against the intended database after its migrations are current. This
command never publishes knowledge or calls an embedding/model provider.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from db.database import async_session_factory
from services.external_sources import (
    fetch_external_fingerprint,
    record_external_fingerprint,
    register_external_url,
)

PROPOSALS = Path(__file__).resolve().parents[1] / "data" / "external_source_proposals.json"


async def seed(*, fetch: bool) -> list[dict[str, str]]:
    manifest = json.loads(PROPOSALS.read_text(encoding="utf-8"))
    if manifest.get("status") != "candidate_only_not_published":
        raise ValueError("external proposal manifest is not marked candidate-only")
    results: list[dict[str, str]] = []
    for source in manifest["sources"]:
        async with async_session_factory() as session:
            row = await register_external_url(
                session, url=source["url"], institution=source["institution"],
                license_note=source["license_note"],
            )
            allowlist_id, url = row.id, row.url
            await session.commit()
        status = "allowlisted"
        if fetch:
            fingerprint = await fetch_external_fingerprint(url)
            async with async_session_factory() as session:
                candidate = await record_external_fingerprint(
                    session, allowlist_id=allowlist_id, fingerprint=fingerprint,
                )
                status = "pending_review" if candidate and candidate.status == "pending" else "unchanged"
                await session.commit()
        results.append({"url": url, "allowlist_id": str(allowlist_id), "status": status})
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Register candidate-only official source URLs")
    parser.add_argument("--fetch", action="store_true", help="Fetch bounded fingerprints and stage pending candidates")
    args = parser.parse_args()
    for item in asyncio.run(seed(fetch=args.fetch)):
        print(json.dumps(item, ensure_ascii=False))


if __name__ == "__main__":
    main()
