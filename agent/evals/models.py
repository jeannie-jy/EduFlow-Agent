"""Typed dataset contract for EduFlowBench."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class OracleSpec(BaseModel):
    """Optional executable oracle for cases with deterministic outcomes."""

    kind: Literal["sorted_array", "final_state"]
    input: dict[str, Any] = Field(default_factory=dict)
    expected: Any = None


class RetrievalExpectation(BaseModel):
    """Expected evidence IDs used by retrieval metrics after RAG is enabled."""

    relevant_document_ids: list[str] = Field(min_length=1)
    k: int = Field(default=5, ge=1, le=50)
    must_abstain_without_evidence: bool = False


class ToolExpectation(BaseModel):
    """Expected observable behavior for a Tool Calling decision case."""

    expected_tools: list[str] = Field(default_factory=list)
    forbidden_tools: list[str] = Field(default_factory=list)
    allow_no_tool: bool = False
    expected_statuses: list[str] = Field(default_factory=lambda: ["ok"])
    max_calls: int = Field(default=8, ge=0, le=32)


class EvalExpectation(BaseModel):
    """Assertions shared by offline deterministic and online semantic graders."""

    required_concepts: list[str] = Field(default_factory=list)
    forbidden_claims: list[str] = Field(default_factory=list)
    min_frames: int = Field(default=1, ge=0)
    max_frames: int = Field(default=30, ge=1)
    final_state: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_frame_range(self) -> "EvalExpectation":
        if self.min_frames > self.max_frames:
            raise ValueError("min_frames must not exceed max_frames")
        return self


class EvalCase(BaseModel):
    """One versioned EduFlowBench input and its expected properties."""

    case_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]+$")
    version: str = "1.0"
    domain: Literal[
        "algorithm",
        "data_structure",
        "operating_system",
        "network",
        "database",
        "software_engineering",
        "custom",
    ]
    difficulty: Literal["beginner", "intermediate", "advanced"]
    topic: str = Field(min_length=2, max_length=500)
    constraints: dict[str, Any] = Field(default_factory=dict)
    materials: list[dict[str, Any]] = Field(default_factory=list)
    expected: EvalExpectation
    oracle: OracleSpec | None = None
    retrieval: RetrievalExpectation | None = None
    tools: ToolExpectation | None = None
    tags: list[str] = Field(default_factory=list)


def load_cases(path: str | Path) -> list[EvalCase]:
    """Load and validate a JSONL dataset, rejecting duplicate case IDs."""

    dataset_path = Path(path)
    cases: list[EvalCase] = []
    seen: set[str] = set()
    for line_number, raw_line in enumerate(dataset_path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            case = EvalCase.model_validate(json.loads(line))
        except Exception as exc:
            raise ValueError(f"invalid case at {dataset_path}:{line_number}: {exc}") from exc
        if case.case_id in seen:
            raise ValueError(f"duplicate case_id at {dataset_path}:{line_number}: {case.case_id}")
        seen.add(case.case_id)
        cases.append(case)
    if not cases:
        raise ValueError(f"dataset contains no cases: {dataset_path}")
    return cases
