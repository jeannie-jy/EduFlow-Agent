"""Read-only publication preflight for a hash-bound core knowledge draft.

This is an evidence gate, not a legal opinion. It never writes to the database,
indexes text, or upgrades a provisional source audit into an approval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from scripts.validate_knowledge_draft import validate_approval, validate_batch


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def check_batch(directory: Path, number: int) -> dict:
    stem = f"batch_{number:03d}"
    draft_path = directory / f"{stem}.json"
    batch = validate_batch(draft_path)
    approval = validate_approval(draft_path, directory / f"{stem}.approval.json")
    digest = approval["draft_sha256"]
    blockers: list[str] = []

    audit_path = directory / f"{stem}.source_audit.json"
    if not audit_path.exists():
        blockers.append("source_audit_missing")
    else:
        audit = _read_json(audit_path)
        if audit.get("batch_id") != batch.batch_id or audit.get("draft_sha256") != digest:
            blockers.append("source_audit_hash_mismatch")
        if set(audit.get("sources", {})) != set(batch.sources):
            blockers.append("source_audit_incomplete")
        if audit.get("status") != "approved" or audit.get("publication_clearance") is not True:
            blockers.append("source_audit_preliminary")

    revision_path = directory / f"{stem}.source_revision_001.json"
    revision_approved = False
    approved_replacements: set[str] = set()
    if revision_path.exists():
        revision = _read_json(revision_path)
        revision_approval_path = directory / f"{stem}.source_revision_001.approval.json"
        if not revision_approval_path.exists():
            blockers.append("source_revision_approval_missing")
        else:
            revision_approval = _read_json(revision_approval_path)
            revision_approved = (
                revision.get("batch_id") == batch.batch_id
                and revision.get("base_draft_sha256") == digest
                and revision_approval.get("batch_id") == batch.batch_id
                and revision_approval.get("base_draft_sha256") == digest
                and revision_approval.get("revision_id") == revision.get("revision_id")
                and revision_approval.get("revision_sha256")
                == hashlib.sha256(revision_path.read_bytes()).hexdigest()
                and revision_approval.get("editorial_review", {}).get("status") == "approved"
                and set(revision_approval.get("editorial_review", {}).get("scope", []))
                == set(revision.get("replacements", {}))
            )
            if not revision_approved:
                blockers.append("source_revision_approval_mismatch")
            else:
                approved_replacements = set(revision["replacements"])

    nist_path = directory / f"{stem}.nist_entry_audit.json"
    supplement_path = directory / f"{stem}.source_supplement_001.json"
    supported_supplements: set[str] = set()
    if supplement_path.exists():
        supplement = _read_json(supplement_path)
        if supplement.get("batch_id") != batch.batch_id or supplement.get("base_draft_sha256") != digest:
            blockers.append("source_supplement_hash_mismatch")
        elif supplement.get("status") == "agent_fact_checked_source_fit":
            supported_supplements = {
                key for key, row in supplement.get("entries", {}).items()
                if key in {entry.source_key for entry in batch.entries}
                and str(row.get("supplemental_url", "")).startswith("https://")
                and str(row.get("finding", "")).startswith("supports_missing_")
            }
    for source_fit_sidecar in sorted(directory.glob(f"{stem}.source_supplement_*.json")):
        source_fit = _read_json(source_fit_sidecar)
        sidecar_id = source_fit_sidecar.stem.removeprefix(f"{stem}.source_supplement_")
        if (
            source_fit.get("batch_id") != batch.batch_id
            or source_fit.get("base_draft_sha256") != digest
        ):
            blockers.append(f"source_supplement_{sidecar_id}_hash_mismatch")
        else:
            for key, row in source_fit.get("entries", {}).items():
                if row.get("editorial_action"):
                    blockers.append(f"source_supplement_pending_editorial_review:{key}")
    if any(entry.source_ref == "nist_dads" for entry in batch.entries):
        if not nist_path.exists():
            blockers.append("nist_entry_audit_missing")
        else:
            nist = _read_json(nist_path)
            nist_keys = {entry.source_key for entry in batch.entries if entry.source_ref == "nist_dads"}
            if nist.get("draft_sha256") != digest or set(nist.get("entries", {})) != nist_keys:
                blockers.append("nist_entry_audit_incomplete")
            unresolved = sorted(
                key for key, entry in nist.get("entries", {}).items()
                if entry.get("finding") != "supports_core_concept"
                and key not in approved_replacements and key not in supported_supplements
            )
            if unresolved:
                blockers.append("source_fit_unresolved:" + ",".join(unresolved))

    if approval.get("source_license_review") != "approved":
        blockers.append("source_license_pending")
    if approval.get("database_import") != "approved_for_staging":
        blockers.append("staging_import_not_authorized")
    if approval.get("embedding_consent") is not True:
        blockers.append("embedding_consent_missing")

    version_path = directory / f"{stem}.version_pin_001.json"
    if version_path.exists():
        version = _read_json(version_path)
        if version.get("batch_id") != batch.batch_id or version.get("base_draft_sha256") != digest:
            blockers.append("version_pin_hash_mismatch")
        if version.get("status") != "approved" or version.get("publication_clearance") is not True:
            blockers.append("version_pins_candidate_only")
    else:
        blockers.append("version_pins_missing")

    return {
        "batch_id": batch.batch_id,
        "draft_sha256": digest,
        "content_approved": True,
        "source_revision_approved": revision_approved,
        "ready_for_staging_import": not any(
            code != "embedding_consent_missing" for code in blockers
        ),
        "ready_for_vector_index": not blockers,
        "blockers": sorted(set(blockers)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "knowledge_drafts")
    parser.add_argument("--batch", type=int, required=True)
    parser.add_argument("--strict", action="store_true", help="exit nonzero while any readiness blocker remains")
    args = parser.parse_args()
    report = check_batch(args.directory, args.batch)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if args.strict and report["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
