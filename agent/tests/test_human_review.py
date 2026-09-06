"""Blinded human-review preparation and calibration scoring tests."""

import json

import pytest

from evals.graders.llm_judge import JUDGE_CRITERIA
from evals.models import EvalCase
from evals.runners.human_review import prepare_review, score_review


def _cases(count: int = 5) -> list[EvalCase]:
    return [
        EvalCase.model_validate(
            {
                "case_id": f"review_case_{index}",
                "domain": "algorithm",
                "difficulty": "beginner",
                "topic": f"算法主题 {index}",
                "expected": {"min_frames": 1, "max_frames": 5},
            }
        )
        for index in range(count)
    ]


def _report(cases: list[EvalCase]) -> dict:
    return {
        "run": {"model": "candidate-secret"},
        "results": [
            {
                "case_id": case.case_id,
                "passed": True,
                "judge": {
                    "judge_model": "judge-secret",
                    "overall_score": 4,
                    "criteria": {
                        criterion: {"score": 4, "reason": "meets rubric"}
                        for criterion in JUDGE_CRITERIA
                    },
                },
            }
            for case in cases
        ],
    }


def _write_artifacts(tmp_path, cases: list[EvalCase]) -> None:
    for case in cases:
        (tmp_path / f"{case.case_id}.json").write_text(
            json.dumps(
                {"topic": case.topic, "frames": [{"frame_id": "f_001"}]},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )


def test_prepare_review_is_deterministic_blinded_and_meets_rate(tmp_path):
    cases = _cases()
    _write_artifacts(tmp_path, cases)

    first = prepare_review(cases, _report(cases), tmp_path, sample_rate=0.4)
    second = prepare_review(cases, _report(cases), tmp_path, sample_rate=0.4)

    assert first == second
    assert first["blind"] is True
    assert first["selection"]["sample_size"] == 2
    assert len(first["reviews"]) == 2
    encoded = json.dumps(first)
    assert "candidate-secret" not in encoded
    assert "judge-secret" not in encoded
    assert '"judge"' not in encoded


def test_score_review_reports_overall_and_per_criterion_calibration(tmp_path):
    cases = _cases()
    report = _report(cases)
    _write_artifacts(tmp_path, cases)
    sheet = prepare_review(cases, report, tmp_path, sample_rate=0.4)
    for review in sheet["reviews"]:
        review["human_scores"] = {criterion: 4 for criterion in JUDGE_CRITERIA}
        review["overall_score"] = 4

    result = score_review(sheet, report, min_rate=0.2)

    assert result["reviewed_count"] == 2
    assert result["review_rate"] == 0.4
    assert result["overall"]["exact_agreement"] == 1.0
    assert set(result["criteria"]) == set(JUDGE_CRITERIA)
    assert all(
        metric["cohen_kappa"] == 1.0 for metric in result["criteria"].values()
    )


def test_prepare_requires_complete_report_and_artifacts(tmp_path):
    cases = _cases(2)
    report = _report(cases)
    with pytest.raises(ValueError, match="artifact is missing"):
        prepare_review(cases, report, tmp_path)

    _write_artifacts(tmp_path, cases)
    report["results"][0].pop("judge")
    with pytest.raises(TypeError, match="no independent Judge"):
        prepare_review(cases, report, tmp_path)


def test_score_rejects_incomplete_labels_and_insufficient_coverage(tmp_path):
    cases = _cases(10)
    report = _report(cases)
    _write_artifacts(tmp_path, cases)
    sheet = prepare_review(cases, report, tmp_path, sample_rate=0.2)

    with pytest.raises(ValueError, match="integer from 1 to 5"):
        score_review(sheet, report, min_rate=0.2)

    sheet["reviews"] = sheet["reviews"][:1]
    with pytest.raises(ValueError, match="coverage below minimum"):
        score_review(sheet, report, min_rate=0.2)
