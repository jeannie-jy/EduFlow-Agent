"""Versioned LLM-judge contract. Invocation belongs in an opt-in online runner."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

JUDGE_PROMPT_VERSION = "eduflow-judge-v2"
JUDGE_CRITERIA = (
    "factual_correctness",
    "clarity",
    "teaching_sequence",
    "topic_alignment",
    "interaction_quality",
    "completeness",
    "audience_fit",
)


class CriterionScore(BaseModel):
    score: int = Field(ge=1, le=5)
    reason: str = Field(min_length=1, max_length=400)


class JudgeResult(BaseModel):
    case_id: str
    prompt_version: str = JUDGE_PROMPT_VERSION
    judge_model: str
    criteria: dict[str, CriterionScore]
    overall_score: float = Field(ge=1, le=5)
    deterministic_passed: bool

    def validated_criteria(self) -> JudgeResult:
        missing = set(JUDGE_CRITERIA) - set(self.criteria)
        unknown = set(self.criteria) - set(JUDGE_CRITERIA)
        if missing or unknown:
            raise ValueError(
                f"judge criteria mismatch: missing={sorted(missing)}, unknown={sorted(unknown)}"
            )
        return self


def build_judge_request(case: dict[str, Any], artifact: dict[str, Any]) -> dict[str, Any]:
    """Build a blinded request without candidate model/vendor identifiers."""

    return {
        "prompt_version": JUDGE_PROMPT_VERSION,
        "instruction": (
            "Evaluate the teaching artifact using every rubric criterion from 1 to 5. "
            "Return only data matching the supplied schema. Do not infer candidate identity. "
            "Keep each reason to one concise sentence (at most 120 Chinese characters); "
            "cite a frame_id or concrete state contradiction when applicable."
        ),
        "rubric": list(JUDGE_CRITERIA),
        "case": case,
        "artifact": artifact,
        "output_schema": JudgeResult.model_json_schema(),
    }


def merge_judge_with_deterministic(
    deterministic: dict[str, Any], judge: JudgeResult
) -> dict[str, Any]:
    """A semantic score can never override a deterministic blocking failure."""

    judge.validated_criteria()
    deterministic_passed = bool(deterministic.get("passed"))
    return {
        **deterministic,
        "passed": deterministic_passed,
        "judge": judge.model_dump(),
        "semantic_score": judge.overall_score,
    }
