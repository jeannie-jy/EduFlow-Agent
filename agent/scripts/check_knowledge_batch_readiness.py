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
        if "man_pipe" in batch.sources and "man_open" in batch.sources:
            man_evidence_path = directory / f"{stem}.man_pages_license_evidence.json"
            if not man_evidence_path.exists():
                blockers.append("man_pages_license_evidence_missing")
            else:
                man_evidence = _read_json(man_evidence_path)
                man_files = man_evidence.get("files", {})
                valid_man_evidence = (
                    audit.get("man_pages_evidence_sha256")
                    == hashlib.sha256(man_evidence_path.read_bytes()).hexdigest()
                    and man_evidence.get("batch_id") == batch.batch_id
                    and man_evidence.get("base_draft_sha256") == digest
                    and man_evidence.get("tag") == "man-pages-6.19"
                    and len(str(man_evidence.get("commit_sha1", ""))) == 40
                    and set(man_files) == {"fork.2", "pipe.2", "open.2"}
                    and all(
                        row.get("spdx") == "Linux-man-pages-copyleft"
                        and len(str(row.get("git_blob_sha1", ""))) == 40
                        for row in man_files.values()
                    )
                    and all(
                        audit.get("sources", {}).get(source_ref, {}).get("evidence_url")
                        == man_files[filename]["source_url"]
                        for source_ref, filename in {"man_pipe": "pipe.2", "man_open": "open.2"}.items()
                    )
                )
                if not valid_man_evidence:
                    blockers.append("man_pages_license_evidence_mismatch")
        if "cp_algorithms" in batch.sources:
            cp_evidence_path = directory / f"{stem}.cp_algorithms_version_evidence.json"
            if not cp_evidence_path.exists():
                blockers.append("cp_algorithms_version_evidence_missing")
            else:
                cp_evidence = _read_json(cp_evidence_path)
                cp_articles = cp_evidence.get("articles", {})
                cp_entries = {
                    entry.source_key: entry for entry in batch.entries
                    if entry.source_ref == "cp_algorithms"
                }
                cp_commit = cp_evidence.get("commit_sha1", "")
                valid_cp_evidence = (
                    audit.get("cp_algorithms_evidence_sha256")
                    == hashlib.sha256(cp_evidence_path.read_bytes()).hexdigest()
                    and cp_evidence.get("batch_id") == batch.batch_id
                    and cp_evidence.get("base_draft_sha256") == digest
                    and len(str(cp_commit)) == 40
                    and set(cp_articles) == set(cp_entries)
                    and len(str(cp_evidence.get("license_file", {}).get("git_blob_sha1", ""))) == 40
                    and all(
                        row.get("published_url") == entry.source_locator.split("#", 1)[0]
                        and row.get("source_url")
                        == f"https://github.com/cp-algorithms/cp-algorithms/blob/"
                        f"{cp_commit}/{row.get('path')}"
                        and len(str(row.get("git_blob_sha1", ""))) == 40
                        for key, entry in cp_entries.items()
                        for row in [cp_articles[key]]
                    )
                    and audit.get("sources", {}).get("cp_algorithms", {}).get("evidence_url")
                    == f"https://github.com/cp-algorithms/cp-algorithms/blob/{cp_commit}/LICENSE"
                )
                if not valid_cp_evidence:
                    blockers.append("cp_algorithms_version_evidence_mismatch")
        if "owasp_threat" in batch.sources:
            owasp_evidence_path = directory / f"{stem}.owasp_version_evidence.json"
            if not owasp_evidence_path.exists():
                blockers.append("owasp_version_evidence_missing")
            else:
                owasp_evidence = _read_json(owasp_evidence_path)
                owasp_page = owasp_evidence.get("page", {})
                owasp_commit = owasp_evidence.get("commit_sha1", "")
                valid_owasp_evidence = (
                    audit.get("owasp_evidence_sha256")
                    == hashlib.sha256(owasp_evidence_path.read_bytes()).hexdigest()
                    and owasp_evidence.get("batch_id") == batch.batch_id
                    and owasp_evidence.get("base_draft_sha256") == digest
                    and len(str(owasp_commit)) == 40
                    and owasp_page.get("path") == "pages/Threat_Modeling.md"
                    and len(str(owasp_page.get("git_blob_sha1", ""))) == 40
                    and owasp_page.get("author_in_frontmatter") == "Victoria Drake"
                    and owasp_page.get("published_url")
                    == audit.get("sources", {}).get("owasp_threat", {}).get("evidence_url")
                    and owasp_page.get("source_url")
                    == f"https://github.com/OWASP/www-community/blob/"
                    f"{owasp_commit}/pages/Threat_Modeling.md"
                )
                if not valid_owasp_evidence:
                    blockers.append("owasp_version_evidence_mismatch")
        if "git_book" in batch.sources:
            pro_git_evidence_path = directory / f"{stem}.pro_git_version_evidence.json"
            if not pro_git_evidence_path.exists():
                blockers.append("pro_git_version_evidence_missing")
            else:
                pro_git_evidence = _read_json(pro_git_evidence_path)
                pro_git_sections = pro_git_evidence.get("sections", {})
                pro_git_commit = pro_git_evidence.get("commit_sha1", "")
                pro_git_keys = {
                    entry.source_key for entry in batch.entries if entry.source_ref == "git_book"
                }
                valid_pro_git_evidence = (
                    audit.get("pro_git_evidence_sha256")
                    == hashlib.sha256(pro_git_evidence_path.read_bytes()).hexdigest()
                    and pro_git_evidence.get("batch_id") == batch.batch_id
                    and pro_git_evidence.get("base_draft_sha256") == digest
                    and len(str(pro_git_commit)) == 40
                    and set(pro_git_sections) == pro_git_keys
                    and pro_git_evidence.get("license_file", {}).get("license_label")
                    == "CC BY-NC-SA 3.0 Unported"
                    and len(str(pro_git_evidence.get("license_file", {}).get("git_blob_sha1", ""))) == 40
                    and all(
                        row.get("source_url")
                        == f"https://github.com/progit/progit2/blob/{pro_git_commit}/"
                        f"{row.get('path')}"
                        and len(str(row.get("git_blob_sha1", ""))) == 40
                        and str(row.get("published_url", "")).startswith(
                            "https://git-scm.com/book/en/v2/"
                        )
                        for row in pro_git_sections.values()
                    )
                    and audit.get("sources", {}).get("git_book", {}).get("evidence_url")
                    == f"https://github.com/progit/progit2/blob/{pro_git_commit}/LICENSE.asc"
                )
                if not valid_pro_git_evidence:
                    blockers.append("pro_git_version_evidence_mismatch")
        if audit.get("status") != "approved" or audit.get("publication_clearance") is not True:
            blockers.append("source_audit_preliminary")

    revision_path = directory / f"{stem}.source_revision_001.json"
    revision_approved = False
    approved_replacements: set[str] = set()
    approved_revision_entries: dict[str, set[str]] = {}
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
                approved_revision_entries[revision["revision_id"]] = approved_replacements

    revision_002_path = directory / f"{stem}.source_revision_002.json"
    revision_002_approved = False
    if revision_002_path.exists():
        revision_002 = _read_json(revision_002_path)
        entries_by_key = {entry.source_key: entry for entry in batch.entries}
        revision_002_approval_path = directory / f"{stem}.source_revision_002.approval.json"
        if not revision_002_approval_path.exists():
            blockers.append("source_revision_002_approval_missing")
        else:
            revision_002_approval = _read_json(revision_002_approval_path)
            revision_002_approved = (
                revision_002.get("batch_id") == batch.batch_id
                and revision_002.get("base_draft_sha256") == digest
                and revision_002.get("revision_id") == f"{batch.batch_id}-source-002"
                and bool(revision_002.get("replacements"))
                and all(
                    key in entries_by_key
                    and replacement.get("old_source_ref") == entries_by_key[key].source_ref
                    and replacement.get("old_source_locator") == entries_by_key[key].source_locator
                    for key, replacement in revision_002["replacements"].items()
                )
                and revision_002_approval.get("batch_id") == batch.batch_id
                and revision_002_approval.get("base_draft_sha256") == digest
                and revision_002_approval.get("revision_id") == revision_002.get("revision_id")
                and revision_002_approval.get("revision_sha256")
                == hashlib.sha256(revision_002_path.read_bytes()).hexdigest()
                and revision_002_approval.get("editorial_review", {}).get("status") == "approved"
                and bool(revision_002_approval.get("editorial_review", {}).get("approved_by"))
                and bool(revision_002_approval.get("editorial_review", {}).get("approved_at_utc"))
                and bool(revision_002_approval.get("editorial_review", {}).get("evidence"))
                and set(revision_002_approval.get("editorial_review", {}).get("scope", []))
                == set(revision_002.get("replacements", {}))
            )
            if not revision_002_approved:
                blockers.append("source_revision_002_approval_mismatch")
            else:
                approved_revision_entries[revision_002["revision_id"]] = set(
                    revision_002["replacements"]
                )

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
                resolution_id = source_fit.get("resolution_revision_id")
                if row.get("editorial_action") and key not in approved_revision_entries.get(
                    resolution_id, set()
                ):
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
        "source_revision_002_approved": revision_002_approved,
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
