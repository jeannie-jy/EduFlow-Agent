"""Validate an unpublished batch of human-reviewable CS knowledge drafts.

This command performs structural checks only. It does not certify facts,
copyright, source version, or human review, and never writes to the database.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from scripts.import_curated_knowledge import SUBJECTS
from services.knowledge_service import stable_source_key


class DraftSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: HttpUrl
    institution: str = Field(min_length=2)
    author: str = Field(min_length=2)
    version: str = Field(min_length=1)
    license_review: str = Field(min_length=2)


class DraftConcept(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_key: str = Field(min_length=3, max_length=240, pattern=r"^[a-z0-9][a-z0-9_-]+$")
    concept: str = Field(min_length=2)
    subject: str
    chapter: str = Field(min_length=2)
    difficulty: int = Field(ge=1, le=5)
    definition: str = Field(min_length=20)
    conditions: list[str] = Field(min_length=1)
    steps: list[str] = Field(min_length=1)
    complexity: str = Field(min_length=2)
    pitfalls: list[str] = Field(min_length=1)
    prerequisites: list[str] = Field(default_factory=list)
    object_types: list[str] = Field(min_length=1)
    animation_types: list[str] = Field(min_length=1)
    source_ref: str
    source_locator: str = Field(min_length=3)
    review_flags: list[str] = Field(default_factory=list)


class DraftBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch_id: str
    status: Literal["draft_pending_human_review"]
    language: Literal["zh-CN"]
    sources: dict[str, DraftSource]
    entries: list[DraftConcept]


def validate_batch(path: Path, *, expected_count: int = 50) -> DraftBatch:
    batch = DraftBatch.model_validate(json.loads(path.read_text(encoding="utf-8")))
    if len(batch.entries) != expected_count:
        raise ValueError(f"expected {expected_count} drafts, got {len(batch.entries)}")
    keys = [entry.source_key for entry in batch.entries]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate draft source_key")
    counts = Counter(entry.subject for entry in batch.entries)
    if set(counts) != SUBJECTS or any(count < 5 for count in counts.values()):
        raise ValueError("all seven core subjects need at least five drafts")

    legacy_path = Path(__file__).resolve().parents[1] / "data" / "seed_knowledge.json"
    legacy = json.loads(legacy_path.read_text(encoding="utf-8"))
    legacy_keys = {stable_source_key(row["concept"], row.get("subject")) for row in legacy}
    if legacy_keys.intersection(keys):
        raise ValueError("draft IDs may not replace legacy stable references")

    prior_keys: set[str] = set()
    for other in path.parent.glob("batch_*.json"):
        if other == path or not re.fullmatch(r"batch_\d+\.json", other.name):
            continue
        other_raw = json.loads(other.read_text(encoding="utf-8"))
        other_keys = {row["source_key"] for row in other_raw.get("entries", [])}
        if other_keys.intersection(keys):
            raise ValueError(f"draft IDs overlap {other.name}")
        if other.name < path.name:
            prior_keys.update(other_keys)

    draft_keys = set(keys)
    for entry in batch.entries:
        if entry.source_ref not in batch.sources:
            raise ValueError(f"missing source reference: {entry.source_key}")
        if entry.source_key in entry.prerequisites:
            raise ValueError(f"self prerequisite: {entry.source_key}")
        for prerequisite in entry.prerequisites:
            if prerequisite not in draft_keys and prerequisite not in legacy_keys and prerequisite not in prior_keys:
                raise ValueError(f"unknown prerequisite {prerequisite} in {entry.source_key}")

    graph = {entry.source_key: set(entry.prerequisites) & draft_keys for entry in batch.entries}
    active: set[str] = set()
    visited: set[str] = set()

    def visit(key: str) -> None:
        if key in active:
            raise ValueError(f"prerequisite cycle at {key}")
        if key in visited:
            return
        active.add(key)
        for prerequisite in graph[key]:
            visit(prerequisite)
        active.remove(key)
        visited.add(key)

    for key in graph:
        visit(key)
    return batch


def validate_approval(batch_path: Path, approval_path: Path) -> dict:
    """Bind a user's content approval to exact draft bytes, not later edits."""
    batch = validate_batch(batch_path)
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(batch_path.read_bytes()).hexdigest()
    if approval.get("batch_id") != batch.batch_id or approval.get("draft_sha256") != digest:
        raise ValueError("approval does not match the current draft")
    review = approval.get("content_review") or {}
    if (
        review.get("status") != "approved"
        or review.get("scope") != "all_50_entries"
        or not review.get("approved_by")
        or not review.get("approved_at_utc")
    ):
        raise ValueError("content approval is incomplete")
    return approval


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--approval", type=Path)
    args = parser.parse_args()
    batch = validate_batch(args.input)
    approval = validate_approval(args.input, args.approval) if args.approval else None
    counts = Counter(entry.subject for entry in batch.entries)
    print(json.dumps({
        "batch_id": batch.batch_id,
        "status": batch.status,
        "draft_count": len(batch.entries),
        "source_count": len(batch.sources),
        "by_subject": dict(counts),
        "content_review": (approval or {}).get("content_review", {}).get("status", "pending"),
        "source_license_review": (approval or {}).get("source_license_review", "pending"),
        "ready_to_publish": False,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
