"""Draft catalog is complete but cannot be mistaken for approved knowledge."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from scripts.check_knowledge_batch_readiness import check_batch
from scripts.import_curated_knowledge import main as import_main
from scripts.import_curated_knowledge import validate_catalog, validate_import_authorization
from scripts.validate_knowledge_draft import validate_approval, validate_batch

BATCH = Path(__file__).resolve().parents[1] / "data" / "knowledge_drafts" / "batch_001.json"
APPROVAL = BATCH.with_name("batch_001.approval.json")
SOURCE_AUDIT = BATCH.with_name("batch_001.source_audit.json")
NIST_AUDIT = BATCH.with_name("batch_001.nist_entry_audit.json")
SECOND_BATCH = BATCH.with_name("batch_002.json")
SECOND_APPROVAL = BATCH.with_name("batch_002.approval.json")
SECOND_SOURCE_AUDIT = BATCH.with_name("batch_002.source_audit.json")
SECOND_NIST_AUDIT = BATCH.with_name("batch_002.nist_entry_audit.json")
SECOND_SOURCE_REVISION = BATCH.with_name("batch_002.source_revision_001.json")
SECOND_SOURCE_REVISION_APPROVAL = BATCH.with_name("batch_002.source_revision_001.approval.json")
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
    assert audit["sources"]["man_pipe"]["disposition"] == "hold_exact_license"


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


def test_second_batch_version_pins_are_candidate_only_and_bound_to_draft():
    batch = validate_batch(SECOND_BATCH)
    approval = validate_approval(SECOND_BATCH, SECOND_APPROVAL)
    pins = json.loads(SECOND_VERSION_PINS.read_text(encoding="utf-8"))
    assert pins["batch_id"] == batch.batch_id
    assert pins["base_draft_sha256"] == approval["draft_sha256"]
    assert pins["status"] == "candidate_version_pins"
    assert pins["publication_clearance"] is False
    assert set(pins["pins"]) <= set(batch.sources)
    assert len(pins["pins"]) == 9
    assert all(row["url"].startswith("https://") for row in pins["pins"].values())
    assert pins["pins"]["python_reference"]["version"] == "Python 3.14 documentation"
    assert pins["pins"]["coverage_py"]["version"] == "Coverage.py 7.16.1 documentation"


def test_second_batch_readiness_gate_distinguishes_editorial_approval_from_release():
    report = check_batch(SECOND_BATCH.parent, 2)
    assert report["content_approved"] is True
    assert report["source_revision_approved"] is True
    assert report["ready_for_staging_import"] is False
    assert report["ready_for_vector_index"] is False
    assert "source_license_pending" in report["blockers"]
    assert "source_audit_preliminary" in report["blockers"]
    assert "version_pins_candidate_only" in report["blockers"]
    assert "embedding_consent_missing" in report["blockers"]
    assert not any(code.startswith("source_fit_unresolved:") for code in report["blockers"])


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
