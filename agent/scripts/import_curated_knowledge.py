"""Validate and import editorially reviewed core concepts into the v2 index.

Example: python -m scripts.import_curated_knowledge --input reviewed.json --dry-run
Publishing requires a human-reviewed record with an identifiable source.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, Field, HttpUrl, field_validator

from db.database import async_session_factory
from evals.evaluation_credentials import online_eval_credential_scope
from services.knowledge_library import _canonical_credential_available, index_source

SUBJECTS = {
    "algorithm", "data_structure", "operating_system", "computer_network",
    "database", "software_engineering", "programming_language",
}


class ReviewedConcept(BaseModel):
    source_key: str = Field(min_length=3, max_length=240, pattern=r"^[a-z0-9][a-z0-9_-]+$")
    concept: str = Field(min_length=2, max_length=200)
    subject: str
    chapter: str = Field(min_length=2, max_length=200)
    difficulty: int = Field(ge=1, le=5)
    definition: str = Field(min_length=20)
    conditions: list[str] = Field(min_length=1)
    steps: list[str] = Field(min_length=1)
    complexity: str = Field(min_length=2)
    pitfalls: list[str] = Field(min_length=1)
    prerequisites: list[str] = Field(default_factory=list)
    object_types: list[str] = Field(min_length=1)
    animation_types: list[str] = Field(min_length=1)
    source_url: HttpUrl
    source_locator: str = Field(min_length=3)
    author: str = Field(min_length=2)
    license: str = Field(min_length=2)
    source_version: str = Field(min_length=1)
    reviewed_by: str = Field(min_length=2)
    reviewed_at: str = Field(min_length=10)

    @field_validator("subject")
    @classmethod
    def valid_subject(cls, value: str) -> str:
        if value not in SUBJECTS:
            raise ValueError("not one of the seven core CS domains")
        return value

    def chunk(self) -> dict[str, str]:
        lines = [
            f"概念：{self.concept}", f"定义：{self.definition}",
            f"适用条件：{'；'.join(self.conditions)}",
            f"关键步骤：{'；'.join(self.steps)}",
            f"复杂度：{self.complexity}",
            f"常见误区：{'；'.join(self.pitfalls)}",
        ]
        return {"section": self.chapter, "locator": self.source_locator,
                "content": "\n".join(lines)}


def validate_catalog(path: Path) -> list[ReviewedConcept]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("catalog must be a JSON array")
    entries = [ReviewedConcept.model_validate(row) for row in raw]
    keys = [entry.source_key for entry in entries]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate stable source keys")
    for entry in entries:
        if entry.source_key in entry.prerequisites:
            raise ValueError(f"self prerequisite: {entry.source_key}")
    return entries


def validate_import_authorization(catalog_path: Path, authorization_path: Path, *, embed: bool) -> dict:
    """Require explicit, hash-bound release evidence before any database write."""
    authorization = json.loads(authorization_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(catalog_path.read_bytes()).hexdigest()
    required = {
        "catalog_sha256": digest,
        "editorial_review": "approved",
        "source_license_review": "approved",
        "staging_import": "approved",
    }
    for key, value in required.items():
        if authorization.get(key) != value:
            raise ValueError(f"import authorization missing or mismatched: {key}")
    if embed and authorization.get("embedding_consent") is not True:
        raise ValueError("embedding consent missing")
    return authorization


async def import_catalog(entries: list[ReviewedConcept], *, embed: bool) -> int:
    if embed and not _canonical_credential_available():
        raise ValueError("canonical 1024-dimension embedding credential required")
    count = 0
    async with async_session_factory() as session:
        for entry in entries:
            await index_source(
                session,
                source_key=entry.source_key, scope="builtin", title=entry.concept,
                version=entry.source_version, chunks=[entry.chunk()],
                subject=entry.subject, difficulty=entry.difficulty,
                metadata={
                    "chapter": entry.chapter, "conditions": entry.conditions,
                    "steps": entry.steps, "complexity": entry.complexity,
                    "pitfalls": entry.pitfalls, "prerequisites": entry.prerequisites,
                    "object_types": entry.object_types,
                    "animation_types": entry.animation_types,
                    "reviewed_by": entry.reviewed_by,
                    "reviewed_at": entry.reviewed_at,
                },
                source_url=str(entry.source_url), source_type="editorial_core",
                author=entry.author, license_name=entry.license,
                allow_embedding=embed, publish=True, review_status="approved",
            )
            count += 1
        await session.commit()
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--embed", action="store_true", help="explicitly permit outbound embedding calls")
    parser.add_argument("--authorization", type=Path, help="hash-bound editorial, license and import approval")
    args = parser.parse_args()
    entries = validate_catalog(args.input)
    if args.dry_run:
        print(f"Validated {len(entries)} editorial records across {len({e.subject for e in entries})} domains")
        return 0
    if args.authorization is None:
        parser.error("--authorization is required for database import")
    validate_import_authorization(args.input, args.authorization, embed=args.embed)
    with online_eval_credential_scope():
        print(f"Imported {asyncio.run(import_catalog(entries, embed=args.embed))} reviewed records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
