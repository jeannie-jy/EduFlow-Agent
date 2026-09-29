"""Draft catalog is complete but cannot be mistaken for approved knowledge."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from scripts.audit_knowledge_source_resolution import audit_batch
from scripts.build_knowledge_review_packet import build_packet
from scripts.check_knowledge_batch_readiness import check_batch
from scripts.import_curated_knowledge import (
    ReviewedConcept,
    validate_catalog,
    validate_import_authorization,
)
from scripts.import_curated_knowledge import main as import_main
from scripts.validate_knowledge_draft import validate_approval, validate_batch

BATCH = Path(__file__).resolve().parents[1] / "data" / "knowledge_drafts" / "batch_001.json"
APPROVAL = BATCH.with_name("batch_001.approval.json")
SOURCE_AUDIT = BATCH.with_name("batch_001.source_audit.json")
NIST_AUDIT = BATCH.with_name("batch_001.nist_entry_audit.json")
SECOND_BATCH = BATCH.with_name("batch_002.json")
SECOND_APPROVAL = BATCH.with_name("batch_002.approval.json")
SECOND_SOURCE_AUDIT = BATCH.with_name("batch_002.source_audit.json")
SECOND_MAN_EVIDENCE = BATCH.with_name("batch_002.man_pages_license_evidence.json")
SECOND_CP_EVIDENCE = BATCH.with_name("batch_002.cp_algorithms_version_evidence.json")
SECOND_OWASP_EVIDENCE = BATCH.with_name("batch_002.owasp_version_evidence.json")
SECOND_PRO_GIT_EVIDENCE = BATCH.with_name("batch_002.pro_git_version_evidence.json")
SECOND_COVERAGE_EVIDENCE = BATCH.with_name("batch_002.coverage_doc_license_evidence.json")
SECOND_NIST_AUDIT = BATCH.with_name("batch_002.nist_entry_audit.json")
SECOND_SOURCE_REVISION = BATCH.with_name("batch_002.source_revision_001.json")
SECOND_SOURCE_REVISION_APPROVAL = BATCH.with_name("batch_002.source_revision_001.approval.json")
SECOND_SOURCE_REVISION_002 = BATCH.with_name("batch_002.source_revision_002.json")
SECOND_SOURCE_REVISION_002_FACTCHECK = BATCH.with_name("batch_002.source_revision_002_factcheck.json")
SECOND_VERSION_PINS = BATCH.with_name("batch_002.version_pin_001.json")


def test_first_batch_has_50_unpublished_entries_across_seven_subjects():
    batch = validate_batch(BATCH)
    assert batch.status == "draft_pending_human_review"
    assert len(batch.entries) == 50
    assert len({entry.subject for entry in batch.entries}) == 7
    assert all(source.license_review.startswith("pending") for source in batch.sources.values())


def test_first_batch_has_no_editorial_approval_fields():
    batch = validate_batch(BATCH)
    assert all(not hasattr(entry, "reviewed_by") for entry in batch.entries)
    assert all(not hasattr(entry, "reviewed_at") for entry in batch.entries)


def test_draft_cannot_be_imported_as_reviewed_catalog():
    with pytest.raises(ValueError, match="JSON array"):
        validate_catalog(BATCH)


def test_curated_import_requires_hash_bound_release_evidence(tmp_path, monkeypatch):
    draft = validate_batch(SECOND_BATCH).entries[0]
    source = validate_batch(SECOND_BATCH).sources[draft.source_ref]
    row = draft.model_dump(exclude={"source_ref", "review_flags"})
    row.update(
        source_url=str(source.url), author=source.author, license="original_summary_link_only",
        source_version=source.version, reviewed_by="test_editor", reviewed_at="2026-09-29",
    )
    catalog = tmp_path / "reviewed.json"
    catalog.write_text(json.dumps([row], ensure_ascii=False), encoding="utf-8")
    assert validate_catalog(catalog)[0].chunk()["locator"] == draft.source_locator
    monkeypatch.setattr("sys.argv", ["import_curated_knowledge", "--input", str(catalog)])
    with pytest.raises(SystemExit, match="2"):
        import_main()

    authorization = tmp_path / "authorization.json"
    evidence = {
        "catalog_sha256": hashlib.sha256(catalog.read_bytes()).hexdigest(),
        "editorial_review": "approved", "source_license_review": "approved",
        "staging_import": "approved", "embedding_consent": False,
    }
    authorization.write_text(json.dumps(evidence), encoding="utf-8")
    assert validate_import_authorization(catalog, authorization, embed=False) == evidence
    with pytest.raises(ValueError, match="embedding consent"):
        validate_import_authorization(catalog, authorization, embed=True)
    catalog.write_bytes(catalog.read_bytes() + b" ")
    with pytest.raises(ValueError, match="catalog_sha256"):
        validate_import_authorization(catalog, authorization, embed=False)


def test_chat_approval_is_bound_to_exact_draft_bytes(tmp_path):
    approval = validate_approval(BATCH, APPROVAL)
    assert approval["content_review"]["status"] == "approved"
    assert approval["source_license_review"] == "pending"
    changed = tmp_path / "changed.json"
    changed.write_bytes(BATCH.read_bytes() + b" ")
    with pytest.raises(ValueError, match="does not match"):
        validate_approval(changed, APPROVAL)


def test_first_batch_preliminary_source_audit_covers_every_source_without_clearance():
    batch = validate_batch(BATCH)
    audit = json.loads(SOURCE_AUDIT.read_text(encoding="utf-8"))
    approval = validate_approval(BATCH, APPROVAL)
    assert audit["batch_id"] == batch.batch_id
    assert audit["draft_sha256"] == approval["draft_sha256"]
    assert audit["status"] == "preliminary_only"
    assert audit["publication_clearance"] is False
    assert set(audit["sources"]) == set(batch.sources)
    assert {entry.source_ref for entry in batch.entries} == set(batch.sources)
    assert all(row["evidence_url"].startswith("https://") for row in audit["sources"].values())
    assert all(row["disposition"] != "approved_for_source_text_import" for row in audit["sources"].values())


def test_nist_entry_audit_identifies_all_15_citations_and_unresolved_source_fit():
    batch = validate_batch(BATCH)
    audit = json.loads(NIST_AUDIT.read_text(encoding="utf-8"))
    assert audit["draft_sha256"] == validate_approval(BATCH, APPROVAL)["draft_sha256"]
    nist_keys = {entry.source_key for entry in batch.entries if entry.source_ref == "nist_dads"}
    assert len(nist_keys) == 15
    assert set(audit["entries"]) == nist_keys
    assert audit["publication_clearance"] is False
    assert all(row["entry_url"].startswith("https://xlinux.nist.gov/dads/HTML/") for row in audit["entries"].values())
    findings = {key: row["finding"] for key, row in audit["entries"].items()}
    assert findings["ds_disjoint_set"] == "wrong_source"
    assert sum(value == "needs_additional_source" for value in findings.values()) == 4


def test_second_batch_has_50_distinct_unreviewed_entries_across_seven_subjects():
    first = validate_batch(BATCH)
    second = validate_batch(SECOND_BATCH)
    assert second.batch_id == "core-cs-002"
    assert second.status == "draft_pending_human_review"
    assert len(second.entries) == 50
    assert {entry.subject for entry in second.entries} == {entry.subject for entry in first.entries}
    assert not ({entry.source_key for entry in first.entries} & {entry.source_key for entry in second.entries})
    assert any("algo_counting_sort" in entry.prerequisites for entry in second.entries)
    assert any("algo_insertion_sort" in entry.prerequisites for entry in second.entries)


def test_second_batch_content_approval_is_bound_to_exact_draft_bytes(tmp_path):
    approval = validate_approval(SECOND_BATCH, SECOND_APPROVAL)
    assert approval["content_review"]["status"] == "approved"
    assert approval["source_license_review"] == "pending"
    (tmp_path / "batch_001.json").write_bytes(BATCH.read_bytes())
    changed = tmp_path / "batch_002.json"
    changed.write_bytes(SECOND_BATCH.read_bytes() + b" ")
    with pytest.raises(ValueError, match="does not match"):
        validate_approval(changed, SECOND_APPROVAL)


def test_second_batch_source_audit_covers_metadata_without_publication_clearance():
    batch = validate_batch(SECOND_BATCH)
    approval = validate_approval(SECOND_BATCH, SECOND_APPROVAL)
    audit = json.loads(SECOND_SOURCE_AUDIT.read_text(encoding="utf-8"))
    assert audit["batch_id"] == batch.batch_id
    assert audit["draft_sha256"] == approval["draft_sha256"]
    assert audit["status"] == "preliminary_only"
    assert audit["publication_clearance"] is False
    assert len(audit["sources"]) == 25
    assert set(audit["sources"]) == set(batch.sources)
    assert {entry.source_ref for entry in batch.entries} == set(batch.sources) - {"kernel_sched"}
    assert all(row["evidence_url"].startswith("https://") for row in audit["sources"].values())
    assert audit["sources"]["git_book"]["disposition"] == "conditional_noncommercial_link_summary"
    assert audit["sources"]["man_pipe"]["disposition"] == "conditional_link_summary"
    assert audit["man_pages_evidence_sha256"] == hashlib.sha256(SECOND_MAN_EVIDENCE.read_bytes()).hexdigest()
    assert audit["cp_algorithms_evidence_sha256"] == hashlib.sha256(SECOND_CP_EVIDENCE.read_bytes()).hexdigest()
    assert audit["owasp_evidence_sha256"] == hashlib.sha256(SECOND_OWASP_EVIDENCE.read_bytes()).hexdigest()
    assert audit["pro_git_evidence_sha256"] == hashlib.sha256(SECOND_PRO_GIT_EVIDENCE.read_bytes()).hexdigest()
    assert audit["coverage_doc_evidence_sha256"] == hashlib.sha256(
        SECOND_COVERAGE_EVIDENCE.read_bytes()
    ).hexdigest()


def test_second_batch_man_pages_license_evidence_is_pinned_to_three_source_blobs():
    evidence = json.loads(SECOND_MAN_EVIDENCE.read_text(encoding="utf-8"))
    assert evidence["base_draft_sha256"] == hashlib.sha256(SECOND_BATCH.read_bytes()).hexdigest()
    assert evidence["tag"] == "man-pages-6.19"
    assert evidence["publication_clearance"] is False
    assert evidence["tag_signature_verified"] is False
    assert set(evidence["files"]) == {"fork.2", "pipe.2", "open.2"}
    assert {row["spdx"] for row in evidence["files"].values()} == {
        "Linux-man-pages-copyleft"
    }


def test_man_pages_license_evidence_tampering_blocks_readiness(tmp_path):
    for path in SECOND_BATCH.parent.glob("batch_*.json"):
        shutil.copy2(path, tmp_path / path.name)
    evidence_path = tmp_path / SECOND_MAN_EVIDENCE.name
    evidence_path.write_bytes(evidence_path.read_bytes() + b" ")
    report = check_batch(tmp_path, 2)
    assert "man_pages_license_evidence_mismatch" in report["blockers"]


def test_cp_algorithms_evidence_pins_all_four_cited_articles():
    batch = validate_batch(SECOND_BATCH)
    evidence = json.loads(SECOND_CP_EVIDENCE.read_text(encoding="utf-8"))
    cp_keys = {entry.source_key for entry in batch.entries if entry.source_ref == "cp_algorithms"}
    assert evidence["base_draft_sha256"] == hashlib.sha256(SECOND_BATCH.read_bytes()).hexdigest()
    assert len(evidence["commit_sha1"]) == 40
    assert set(evidence["articles"]) == cp_keys
    assert all(len(row["git_blob_sha1"]) == 40 for row in evidence["articles"].values())
    assert evidence["publication_clearance"] is False


def test_cp_algorithms_evidence_tampering_blocks_readiness(tmp_path):
    for path in SECOND_BATCH.parent.glob("batch_*.json"):
        shutil.copy2(path, tmp_path / path.name)
    evidence_path = tmp_path / SECOND_CP_EVIDENCE.name
    evidence_path.write_bytes(evidence_path.read_bytes() + b" ")
    report = check_batch(tmp_path, 2)
    assert "cp_algorithms_version_evidence_mismatch" in report["blockers"]


def test_owasp_evidence_pins_page_author_and_revision():
    evidence = json.loads(SECOND_OWASP_EVIDENCE.read_text(encoding="utf-8"))
    assert evidence["base_draft_sha256"] == hashlib.sha256(SECOND_BATCH.read_bytes()).hexdigest()
    assert len(evidence["commit_sha1"]) == 40
    assert len(evidence["page"]["git_blob_sha1"]) == 40
    assert evidence["page"]["author_in_frontmatter"] == "Victoria Drake"
    assert evidence["publication_clearance"] is False


def test_owasp_evidence_tampering_blocks_readiness(tmp_path):
    for path in SECOND_BATCH.parent.glob("batch_*.json"):
        shutil.copy2(path, tmp_path / path.name)
    evidence_path = tmp_path / SECOND_OWASP_EVIDENCE.name
    evidence_path.write_bytes(evidence_path.read_bytes() + b" ")
    report = check_batch(tmp_path, 2)
    assert "owasp_version_evidence_mismatch" in report["blockers"]


def test_pro_git_evidence_pins_two_sections_and_noncommercial_license():
    evidence = json.loads(SECOND_PRO_GIT_EVIDENCE.read_text(encoding="utf-8"))
    assert evidence["base_draft_sha256"] == hashlib.sha256(SECOND_BATCH.read_bytes()).hexdigest()
    assert len(evidence["commit_sha1"]) == 40
    assert set(evidence["sections"]) == {"se_branching", "se_merge_conflict"}
    assert evidence["license_file"]["license_label"] == "CC BY-NC-SA 3.0 Unported"
    assert evidence["publication_clearance"] is False


def test_pro_git_evidence_tampering_blocks_readiness(tmp_path):
    for path in SECOND_BATCH.parent.glob("batch_*.json"):
        shutil.copy2(path, tmp_path / path.name)
    evidence_path = tmp_path / SECOND_PRO_GIT_EVIDENCE.name
    evidence_path.write_bytes(evidence_path.read_bytes() + b" ")
    report = check_batch(tmp_path, 2)
    assert "pro_git_version_evidence_mismatch" in report["blockers"]


def test_coverage_document_license_evidence_pins_cited_source_files():
    evidence = json.loads(SECOND_COVERAGE_EVIDENCE.read_text(encoding="utf-8"))
    assert evidence["base_draft_sha256"] == hashlib.sha256(SECOND_BATCH.read_bytes()).hexdigest()
    assert evidence["tag"] == "7.16.1"
    assert set(evidence["files"]) == {
        "doc/index.rst", "doc/branch.rst", "NOTICE.txt", "LICENSE.txt"
    }
    assert all(
        row["license_notice"] == "Apache-2.0 notice in first source line"
        for path, row in evidence["files"].items() if path.startswith("doc/")
    )
    assert evidence["publication_clearance"] is False


def test_coverage_document_license_evidence_tampering_blocks_readiness(tmp_path):
    for path in SECOND_BATCH.parent.glob("batch_*.json"):
        shutil.copy2(path, tmp_path / path.name)
    evidence_path = tmp_path / SECOND_COVERAGE_EVIDENCE.name
    evidence_path.write_bytes(evidence_path.read_bytes() + b" ")
    report = check_batch(tmp_path, 2)
    assert "coverage_doc_license_evidence_mismatch" in report["blockers"]


def test_second_batch_nist_audit_flags_third_party_and_wrong_locators():
    batch = validate_batch(SECOND_BATCH)
    audit = json.loads(SECOND_NIST_AUDIT.read_text(encoding="utf-8"))
    assert audit["draft_sha256"] == validate_approval(SECOND_BATCH, SECOND_APPROVAL)["draft_sha256"]
    nist_keys = {entry.source_key for entry in batch.entries if entry.source_ref == "nist_dads"}
    assert len(nist_keys) == 11
    assert set(audit["entries"]) == nist_keys
    assert audit["publication_clearance"] is False
    assert audit["entries"]["algo_lcs"]["finding"] == "third_party_copyright_and_incomplete_source"
    assert audit["entries"]["algo_a_star"]["finding"] == "wrong_source"
    assert audit["entries"]["algo_a_star"]["entry_url"] is None
    assert audit["entries"]["ds_circular_buffer"]["finding"] == "related_but_not_exact"


def test_second_batch_source_revision_is_bound_to_approved_snapshot_and_not_publishable():
    batch = validate_batch(SECOND_BATCH)
    approval = validate_approval(SECOND_BATCH, SECOND_APPROVAL)
    revision = json.loads(SECOND_SOURCE_REVISION.read_text(encoding="utf-8"))
    assert revision["batch_id"] == batch.batch_id
    assert revision["base_draft_sha256"] == approval["draft_sha256"]
    assert revision["status"] == "pending_editorial_source_review"
    assert revision["publication_clearance"] is False
    entries = {entry.source_key: entry for entry in batch.entries}
    assert set(revision["replacements"]) == {"algo_a_star", "algo_lcs", "ds_circular_buffer"}
    for key, replacement in revision["replacements"].items():
        assert replacement["old_source_ref"] == entries[key].source_ref
        assert replacement["old_source_locator"] == entries[key].source_locator
        assert replacement["source"]["url"].startswith("https://")
        assert replacement["source_locator"]
        assert set(replacement) <= {
            "old_source_ref", "old_source_locator", "source", "source_locator",
            "evidence_url", "license_evidence_url", "reason", "editorial_check",
        }
    assert approval["source_license_review"] == "pending"


def test_second_batch_source_revision_approval_is_bound_to_exact_revision_bytes():
    revision = json.loads(SECOND_SOURCE_REVISION.read_text(encoding="utf-8"))
    approval = json.loads(SECOND_SOURCE_REVISION_APPROVAL.read_text(encoding="utf-8"))
    assert approval["batch_id"] == revision["batch_id"]
    assert approval["revision_id"] == revision["revision_id"]
    assert approval["base_draft_sha256"] == revision["base_draft_sha256"]
    assert approval["revision_sha256"] == hashlib.sha256(SECOND_SOURCE_REVISION.read_bytes()).hexdigest()
    assert approval["editorial_review"]["status"] == "approved"
    assert set(approval["editorial_review"]["scope"]) == set(revision["replacements"])
    assert approval["source_license_review"] == "pending"
    assert approval["publication_clearance"] is False
    assert approval["database_import"] == "not_started"
    assert approval["embedding_consent"] is False


def test_second_source_revision_is_reviewable_but_not_yet_approved():
    batch = validate_batch(SECOND_BATCH)
    revision = json.loads(SECOND_SOURCE_REVISION_002.read_text(encoding="utf-8"))
    entries = {entry.source_key: entry for entry in batch.entries}
    assert revision["batch_id"] == batch.batch_id
    assert revision["base_draft_sha256"] == hashlib.sha256(SECOND_BATCH.read_bytes()).hexdigest()
    assert revision["status"] == "pending_editorial_source_review"
    assert revision["publication_clearance"] is False
    assert set(revision["replacements"]) == {"os_copy_on_write", "net_udp_datagram"}
    for key, replacement in revision["replacements"].items():
        assert replacement["old_source_ref"] == entries[key].source_ref
        assert replacement["old_source_locator"] == entries[key].source_locator
        assert replacement["source"]["url"].startswith("https://")
        assert replacement["source_locator"]
    assert "IPv6" not in revision["replacements"]["net_udp_datagram"]["source_locator"]


def test_second_source_revision_factcheck_is_hash_bound_and_not_an_approval():
    factcheck = json.loads(SECOND_SOURCE_REVISION_002_FACTCHECK.read_text(encoding="utf-8"))
    assert factcheck["base_draft_sha256"] == hashlib.sha256(SECOND_BATCH.read_bytes()).hexdigest()
    assert factcheck["source_revision_sha256"] == hashlib.sha256(
        SECOND_SOURCE_REVISION_002.read_bytes()
    ).hexdigest()
    assert factcheck["status"] == "agent_factual_source_check_not_editorial_approval"
    assert factcheck["publication_clearance"] is False
    assert set(factcheck["checks"]) == {"os_copy_on_write", "net_udp_datagram"}
    assert "copyright notice" in factcheck["checks"]["os_copy_on_write"]["supplements"][2][
        "license_review"
    ]


def test_second_source_revision_gate_requires_exact_approved_bytes(tmp_path):
    for path in SECOND_BATCH.parent.glob("batch_*.json"):
        shutil.copy2(path, tmp_path / path.name)
    revision_path = tmp_path / SECOND_SOURCE_REVISION_002.name
    revision = json.loads(revision_path.read_text(encoding="utf-8"))
    approval = {
        "batch_id": revision["batch_id"],
        "base_draft_sha256": revision["base_draft_sha256"],
        "revision_id": revision["revision_id"],
        "revision_sha256": hashlib.sha256(revision_path.read_bytes()).hexdigest(),
        "editorial_review": {
            "status": "approved",
            "scope": list(revision["replacements"]),
            "approved_by": "synthetic_test_reviewer",
            "approved_at_utc": "2026-09-29T00:00:00Z",
            "evidence": "test fixture only",
        },
    }
    (tmp_path / "batch_002.source_revision_002.approval.json").write_text(
        json.dumps(approval), encoding="utf-8"
    )
    report = check_batch(tmp_path, 2)
    assert report["source_revision_002_approved"] is True
    assert not any("source_supplement_pending_editorial_review" in code for code in report["blockers"])
    assert report["ready_for_staging_import"] is False

    revision_path.write_bytes(revision_path.read_bytes() + b" ")
    report = check_batch(tmp_path, 2)
    assert report["source_revision_002_approved"] is False
    assert "source_revision_002_approval_mismatch" in report["blockers"]
    assert "source_supplement_pending_editorial_review:os_copy_on_write" in report["blockers"]


def test_second_batch_version_pins_are_candidate_only_and_bound_to_draft():
    batch = validate_batch(SECOND_BATCH)
    approval = validate_approval(SECOND_BATCH, SECOND_APPROVAL)
    pins = json.loads(SECOND_VERSION_PINS.read_text(encoding="utf-8"))
    assert pins["batch_id"] == batch.batch_id
    assert pins["base_draft_sha256"] == approval["draft_sha256"]
    assert pins["status"] == "verified_candidate_sections"
    assert pins["publication_clearance"] is False
    assert set(pins["pins"]) <= set(batch.sources) | {
        "man_pages", "berkeley_cs188", "mit_ocw_6006", "rfc8200",
    }
    assert len(pins["pins"]) == 26
    assert all(row["url"].startswith("https://") for row in pins["pins"].values())
    assert pins["pins"]["python_reference"]["version"] == "Python 3.14.7 documentation"
    assert pins["pins"]["coverage_py"]["version"] == "Coverage.py 7.16.1 documentation"
    assert pins["pins"]["postgres16"]["locators"]["db_analyze_statistics"].endswith("planner-stats.html")
    assert pins["pins"]["man_pages"]["locators"]["os_copy_on_write_candidate"].endswith("fork.2.html#NOTES")
    assert pins["pins"]["rfc8200"]["version"] == "RFC 8200"


def test_second_batch_readiness_gate_distinguishes_editorial_approval_from_release():
    report = check_batch(SECOND_BATCH.parent, 2)
    assert report["content_approved"] is True
    assert report["source_revision_approved"] is True
    assert report["source_revision_002_approved"] is False
    assert report["ready_for_staging_import"] is False
    assert report["ready_for_vector_index"] is False
    assert "source_license_pending" in report["blockers"]
    assert "source_audit_preliminary" in report["blockers"]
    assert "version_pins_candidate_only" in report["blockers"]
    assert "embedding_consent_missing" in report["blockers"]
    assert "source_revision_002_approval_missing" in report["blockers"]
    assert "source_supplement_pending_editorial_review:os_copy_on_write" in report["blockers"]
    assert "source_supplement_pending_editorial_review:net_udp_datagram" in report["blockers"]
    assert not any(code.startswith("source_fit_unresolved:") for code in report["blockers"])


def test_second_batch_source_resolution_covers_all_50_without_implying_release():
    report = audit_batch(SECOND_BATCH.parent, 2)
    assert report["count"] == 50
    assert report["release_ready"] is False
    assert report["candidate_revisions"] == 2
    assert report["rows_with_citation_issues"] == 2
    assert report["rows_with_version_warnings"] == 9
    rows = {row["source_key"]: row for row in report["entries"]}
    assert rows["algo_counting_sort"]["source_url"].endswith("/countingsort.html")
    assert "/blob/" in rows["algo_edmonds_karp"]["source_url"]
    assert "/docs/16/transaction-iso.html" in rows["db_serializable_isolation"]["source_url"]
    assert "/3.14/reference/datamodel.html" in rows["pl_python_iterator_protocol"]["source_url"]
    assert rows["algo_a_star"]["source_status"] == "approved_revision"
    assert rows["os_copy_on_write"]["source_status"] == "proposed_revision"
    assert rows["net_udp_datagram"]["source_status"] == "proposed_revision"
    assert "unversioned_nist_page_no_content_snapshot" in rows["algo_counting_sort"]["version_warnings"]
    assert rows["algo_counting_sort"]["response_sha256"] == {}
    assert len(rows["algo_a_star"]["response_sha256"]) == 1
    assert len(rows["algo_radix_sort"]["response_sha256"]) == 1
    assert len(rows["algo_kruskal"]["response_sha256"]) == 1
    assert rows["algo_a_star"]["version_warnings"] == ["unversioned_source_no_content_snapshot"]
    assert all(row["source_url"].startswith("https://") for row in rows.values())


def test_source_resolution_rejects_response_evidence_bound_to_another_draft(tmp_path):
    for path in SECOND_BATCH.parent.glob("batch_*.json"):
        shutil.copy2(path, tmp_path / path.name)
    path = tmp_path / "batch_002.web_response_evidence_001.json"
    evidence = json.loads(path.read_text(encoding="utf-8"))
    evidence["base_draft_sha256"] = "0" * 64
    path.write_text(json.dumps(evidence), encoding="utf-8")
    with pytest.raises(ValueError, match="bound to another draft"):
        audit_batch(tmp_path, 2)


def test_second_batch_review_packet_covers_50_without_becoming_importable():
    packet = build_packet(SECOND_BATCH.parent, 2)
    assert packet["count"] == 50
    assert packet["publication_clearance"] is False
    assert "source_license_pending" in packet["global_blockers"]
    rows = {row["source_key"]: row for row in packet["entries"]}
    assert len(rows) == 50
    assert rows["algo_a_star"]["source"]["candidate_status"] == "approved_revision"
    assert rows["os_copy_on_write"]["source"]["candidate_status"] == "proposed_revision"
    assert rows["net_udp_datagram"]["source"]["url"].endswith("/rfc768.html")
    assert rows["algo_counting_sort"]["preliminary_license"]["disposition"] == "hold_per_entry"
    assert all("reviewed_by" not in row and "license" not in row for row in packet["entries"])
    with pytest.raises(ValidationError):
        ReviewedConcept.model_validate(rows["algo_a_star"])


def test_readiness_gate_detects_tampered_source_revision(tmp_path):
    for path in SECOND_BATCH.parent.glob("batch_*.json"):
        shutil.copy2(path, tmp_path / path.name)
    revision = tmp_path / SECOND_SOURCE_REVISION.name
    revision.write_bytes(revision.read_bytes() + b" ")
    report = check_batch(tmp_path, 2)
    assert report["source_revision_approved"] is False
    assert "source_revision_approval_mismatch" in report["blockers"]


def test_first_batch_rejects_missing_source(tmp_path):
    raw = json.loads(BATCH.read_text(encoding="utf-8"))
    raw["entries"][0]["source_ref"] = "not-a-source"
    modified = tmp_path / "invalid.json"
    modified.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="missing source reference"):
        validate_batch(modified)
