"""Draft catalog is complete but cannot be mistaken for approved knowledge."""

import json
from pathlib import Path

import pytest

from scripts.validate_knowledge_draft import validate_approval, validate_batch
from scripts.import_curated_knowledge import validate_catalog


BATCH = Path(__file__).resolve().parents[1] / "data" / "knowledge_drafts" / "batch_001.json"
APPROVAL = BATCH.with_name("batch_001.approval.json")
SOURCE_AUDIT = BATCH.with_name("batch_001.source_audit.json")
SECOND_BATCH = BATCH.with_name("batch_002.json")


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


def test_first_batch_rejects_missing_source(tmp_path):
    raw = json.loads(BATCH.read_text(encoding="utf-8"))
    raw["entries"][0]["source_ref"] = "not-a-source"
    modified = tmp_path / "invalid.json"
    modified.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="missing source reference"):
        validate_batch(modified)
