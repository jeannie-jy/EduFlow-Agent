"""Preview or create a signed audit archive and optionally purge verified rows."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from config import get_settings
from db.database import async_session_factory, close_database
from db.models import AuditEvent
from services.artifact_store import get_artifact_store
from services.audit_archive import archive_audit_events


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write archive objects")
    parser.add_argument(
        "--purge-after-verify",
        action="store_true",
        help="delete only the exact rows downloaded and cryptographically verified",
    )
    parser.add_argument("--retention-days", type=int, help="override configured retention days")
    parser.add_argument("--max-events", type=int, help="bounded oldest-first batch size")
    return parser.parse_args()


async def async_main() -> int:
    try:
        args = parse_args()
        if args.purge_after_verify and not args.apply:
            raise ValueError("--purge-after-verify requires --apply")
        settings = get_settings()
        retention_days = args.retention_days or settings.audit_retention_days
        max_events = args.max_events or settings.audit_archive_max_events
        if retention_days < 7 or max_events < 1 or max_events > 100000:
            raise ValueError("retention-days must be >=7 and max-events must be 1..100000")
        before = datetime.now(timezone.utc) - timedelta(days=retention_days)
        async with async_session_factory() as session:
            if not args.apply:
                count = int(await session.scalar(
                    select(func.count(AuditEvent.id)).where(AuditEvent.created_at < before)
                ) or 0)
                report = {
                    "apply": False,
                    "before": before.isoformat(),
                    "eligible_event_count": count,
                    "next_batch_size": min(count, max_events),
                }
                await session.rollback()
            else:
                signing_key = settings.audit_archive_hmac_key.encode("utf-8")
                report = await archive_audit_events(
                    session,
                    get_artifact_store(),
                    before=before,
                    signing_key=signing_key,
                    max_events=max_events,
                    purge_after_verify=args.purge_after_verify,
                )
                report["apply"] = True
                report["before"] = before.isoformat()
                await session.commit()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    finally:
        await close_database()


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
