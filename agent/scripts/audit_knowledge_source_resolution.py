"""Resolve every draft concept to reviewable source URLs without writing or indexing.

This is a candidate citation inventory. It does not approve a source, grant reuse
rights, or create an importable catalog.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.check_knowledge_batch_readiness import check_batch
from scripts.validate_knowledge_draft import validate_batch


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def audit_batch(directory: Path, number: int) -> dict:
    if number != 2:
        raise ValueError("source resolution inventory is implemented for batch 002 only")
    stem = f"batch_{number:03d}"
    batch = validate_batch(directory / f"{stem}.json")
    readiness = check_batch(directory, number)
    if any(
        "evidence_missing" in blocker or "evidence_mismatch" in blocker
        or blocker == "version_pin_hash_mismatch"
        for blocker in readiness["blockers"]
    ):
        raise ValueError("source evidence is missing or does not match its audit")
    pins = _json(directory / f"{stem}.version_pin_001.json")["pins"]
    nist = _json(directory / f"{stem}.nist_entry_audit.json")["entries"]
    cp_evidence = _json(directory / f"{stem}.cp_algorithms_version_evidence.json")
    cp = cp_evidence["articles"]
    pro_git_evidence = _json(directory / f"{stem}.pro_git_version_evidence.json")
    pro_git = pro_git_evidence["sections"]
    owasp_evidence = _json(directory / f"{stem}.owasp_version_evidence.json")
    owasp = owasp_evidence["page"]
    man = _json(directory / f"{stem}.man_pages_license_evidence.json")["files"]
    supplement = _json(directory / f"{stem}.source_supplement_001.json")["entries"]
    revisions: dict[str, tuple[dict, bool, str]] = {}
    for ordinal, approved_key in ((1, "source_revision_approved"), (2, "source_revision_002_approved")):
        path = directory / f"{stem}.source_revision_{ordinal:03d}.json"
        if not path.exists():
            continue
        revision = _json(path)
        for key, replacement in revision["replacements"].items():
            if key in revisions:
                raise ValueError(f"overlapping source revisions for {key}")
            revisions[key] = (replacement, readiness[approved_key], revision["revision_id"])

    kernel_urls = {
        "os_tlb": "https://docs.kernel.org/6.19/mm/page_tables.html",
        "os_lru_page_replacement": "https://docs.kernel.org/6.19/mm/multigen_lru.html",
        "os_priority_inversion": "https://docs.kernel.org/6.19/locking/rt-mutex.html",
        "os_rw_lock": "https://docs.kernel.org/6.19/locking/locktypes.html#rwlock_t",
    }
    man_files = {"man_pipe": "pipe.2", "man_open": "open.2"}
    rows = []
    for entry in batch.entries:
        source = batch.sources[entry.source_ref]
        pin = pins.get(entry.source_ref, {})
        url = str(source.url)
        version = pin.get("version", source.version)
        locator = entry.source_locator
        status = "draft_source"
        issues: list[str] = []
        version_warnings: list[str] = []
        supporting_urls: list[str] = []

        if entry.source_key in revisions:
            replacement, approved, revision_id = revisions[entry.source_key]
            url = replacement["source"]["url"]
            version = replacement["source"]["version"]
            locator = replacement["source_locator"]
            status = "approved_revision" if approved else "proposed_revision"
            supporting_urls.extend(
                row["url"] for row in replacement.get("supplemental_evidence", [])
            )
            if not approved:
                issues.append(f"editorial_review_pending:{revision_id}")
            if "accessed" in version.casefold():
                version_warnings.append("unversioned_source_no_content_snapshot")
        elif entry.source_ref == "nist_dads":
            url = nist[entry.source_key]["entry_url"] or ""
            version_warnings.append("unversioned_nist_page_no_content_snapshot")
            if not url:
                issues.append("exact_nist_page_missing")
        elif entry.source_ref == "cp_algorithms":
            url = cp[entry.source_key]["source_url"]
            version = f"Git commit {cp_evidence['commit_sha1']}"
        elif entry.source_ref == "git_book":
            url = pro_git[entry.source_key]["source_url"]
            version = f"Git commit {pro_git_evidence['commit_sha1']}"
        elif entry.source_ref == "owasp_threat":
            url = owasp["source_url"]
            version = f"Git commit {owasp_evidence['commit_sha1']}"
        elif entry.source_ref in man_files:
            url = man[man_files[entry.source_ref]]["source_url"]
        elif entry.source_key in kernel_urls:
            url = kernel_urls[entry.source_key]
        elif entry.source_ref == "coverage_py":
            url = pin["locators"]["branch_measurement"]
        else:
            pinned_locator = pin.get("locators", {}).get(entry.source_key)
            if isinstance(pinned_locator, str) and pinned_locator.startswith("https://"):
                url = pinned_locator
            elif pin.get("url"):
                url = pin["url"]

        if entry.source_key in supplement:
            supporting_urls.append(supplement[entry.source_key]["supplemental_url"])
            version_warnings.append("supplemental_web_page_no_content_snapshot")
        if not url.startswith("https://"):
            issues.append("source_url_missing")
        if not locator:
            issues.append("source_locator_missing")
        rows.append({
            "source_key": entry.source_key,
            "source_ref": entry.source_ref,
            "source_url": url,
            "source_version": version,
            "source_locator": locator,
            "source_status": status,
            "supporting_urls": supporting_urls,
            "issues": issues,
            "version_warnings": version_warnings,
        })

    return {
        "batch_id": batch.batch_id,
        "draft_sha256": readiness["draft_sha256"],
        "release_ready": readiness["ready_for_staging_import"],
        "count": len(rows),
        "candidate_revisions": sum(row["source_status"] == "proposed_revision" for row in rows),
        "rows_with_citation_issues": sum(bool(row["issues"]) for row in rows),
        "rows_with_version_warnings": sum(bool(row["version_warnings"]) for row in rows),
        "entries": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "knowledge_drafts")
    parser.add_argument("--batch", type=int, required=True)
    parser.add_argument("--strict", action="store_true", help="fail if citation or version issues remain")
    args = parser.parse_args()
    report = audit_batch(args.directory, args.batch)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if args.strict and (
        report["rows_with_citation_issues"] or report["rows_with_version_warnings"]
    ) else 0


if __name__ == "__main__":
    raise SystemExit(main())
