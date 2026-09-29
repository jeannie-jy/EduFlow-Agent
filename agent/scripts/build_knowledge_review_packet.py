"""Build a read-only, non-importable per-entry editorial packet for batch 002.

The packet combines the immutable approved draft with candidate citation and
preliminary license evidence. It deliberately omits ReviewedConcept's license,
reviewed_by and reviewed_at fields, and never writes to a database or file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from scripts.audit_knowledge_source_resolution import audit_batch
from scripts.check_knowledge_batch_readiness import check_batch
from scripts.validate_knowledge_draft import validate_batch


def build_packet(directory: Path, number: int) -> dict:
    citations = audit_batch(directory, number)
    readiness = check_batch(directory, number)
    batch = validate_batch(directory / f"batch_{number:03d}.json")
    audit = json.loads(
        (directory / f"batch_{number:03d}.source_audit.json").read_text(encoding="utf-8")
    )
    if audit.get("batch_id") != batch.batch_id or audit.get("draft_sha256") != citations["draft_sha256"]:
        raise ValueError("preliminary license audit is not bound to this draft")
    if len(citations["entries"]) != len(batch.entries):
        raise ValueError("citation inventory does not cover every draft entry")
    citation_by_key = {item["source_key"]: item for item in citations["entries"]}
    if set(citation_by_key) != {entry.source_key for entry in batch.entries}:
        raise ValueError("citation inventory keys do not match draft keys")
    nist = json.loads(
        (directory / f"batch_{number:03d}.nist_entry_audit.json").read_text(encoding="utf-8")
    )
    supplement = json.loads(
        (directory / f"batch_{number:03d}.source_supplement_001.json").read_text(encoding="utf-8")
    )
    if nist.get("draft_sha256") != citations["draft_sha256"] or supplement.get(
        "base_draft_sha256"
    ) != citations["draft_sha256"]:
        raise ValueError("source-fit evidence is bound to another draft")

    revisions: dict[str, dict] = {}
    for ordinal in (1, 2):
        path = directory / f"batch_{number:03d}.source_revision_{ordinal:03d}.json"
        if path.exists():
            revision = json.loads(path.read_text(encoding="utf-8"))
            if revision.get("base_draft_sha256") != citations["draft_sha256"]:
                raise ValueError("source revision is bound to another draft")
            for key, replacement in revision["replacements"].items():
                if key in revisions:
                    raise ValueError(f"overlapping source revisions for {key}")
                revisions[key] = replacement

    factcheck_path = directory / f"batch_{number:03d}.source_revision_002_factcheck.json"
    factcheck = json.loads(factcheck_path.read_text(encoding="utf-8"))
    revision_002_path = directory / f"batch_{number:03d}.source_revision_002.json"
    if (
        factcheck.get("base_draft_sha256") != citations["draft_sha256"]
        or factcheck.get("source_revision_sha256")
        != hashlib.sha256(revision_002_path.read_bytes()).hexdigest()
    ):
        raise ValueError("source revision factcheck is not bound to the cited revision")

    entries = []
    for draft in batch.entries:
        citation = citation_by_key[draft.source_key]
        replacement = revisions.get(draft.source_key)
        source = replacement["source"] if replacement else batch.sources[draft.source_ref].model_dump(
            mode="json"
        )
        policy = audit["sources"][draft.source_ref]
        source_fit = {}
        if draft.source_key in nist["entries"]:
            source_fit["original_nist_audit"] = nist["entries"][draft.source_key]
        if replacement:
            source_fit["revision_reason"] = replacement["reason"]
            source_fit["revision_editorial_check"] = replacement["editorial_check"]
        if draft.source_key in supplement["entries"]:
            source_fit["supplement_001"] = supplement["entries"][draft.source_key]
        if draft.source_key in factcheck["checks"]:
            source_fit["revision_002_factcheck"] = factcheck["checks"][draft.source_key]
        entries.append({
            "source_key": draft.source_key,
            "concept": draft.concept,
            "subject": draft.subject,
            "chapter": draft.chapter,
            "difficulty": draft.difficulty,
            "definition": draft.definition,
            "conditions": draft.conditions,
            "steps": draft.steps,
            "complexity": draft.complexity,
            "pitfalls": draft.pitfalls,
            "prerequisites": draft.prerequisites,
            "object_types": draft.object_types,
            "animation_types": draft.animation_types,
            "draft_review_flags": draft.review_flags,
            "source": {
                "url": citation["source_url"],
                "locator": citation["source_locator"],
                "version": citation["source_version"],
                "author": source["author"],
                "institution": source["institution"],
                "candidate_status": citation["source_status"],
                "supporting_urls": citation["supporting_urls"],
                "response_sha256": citation["response_sha256"],
            },
            "preliminary_license": {
                "label": policy["license_label"] if draft.source_key not in revisions else source["license_review"],
                "disposition": policy["disposition"] if draft.source_key not in revisions else "source_revision_not_a_license_approval",
                "required_action": policy["required_action"] if draft.source_key not in revisions
                else "Review replacement source license and citation fit separately before import.",
            },
            "citation_issues": citation["issues"],
            "version_warnings": citation["version_warnings"],
            "source_fit_evidence": source_fit,
            "editorial_release_status": "not_approved_for_import",
        })

    return {
        "batch_id": batch.batch_id,
        "draft_sha256": citations["draft_sha256"],
        "kind": "candidate_editorial_review_packet_not_importable_catalog",
        "publication_clearance": False,
        "count": len(entries),
        "global_blockers": readiness["blockers"],
        "entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--directory", type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "knowledge_drafts",
    )
    parser.add_argument("--batch", type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(build_packet(args.directory, args.batch), ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
