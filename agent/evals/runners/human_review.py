"""Prepare blinded human review sheets and score Judge calibration."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evals.graders.human_calibration import calibration_report
from evals.graders.llm_judge import JUDGE_CRITERIA
from evals.models import EvalCase, load_cases


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected a JSON object: {path}")
    return payload


def _result_map(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    results = report.get("results")
    if not isinstance(results, list):
        raise TypeError("online report has no results list")
    mapped: dict[str, dict[str, Any]] = {}
    for result in results:
        case_id = result.get("case_id") if isinstance(result, dict) else None
        if not isinstance(case_id, str) or case_id in mapped:
            raise ValueError("online report contains invalid or duplicate case IDs")
        mapped[case_id] = result
    return mapped


def _sample_key(seed: str, case_id: str) -> str:
    return hashlib.sha256(f"{seed}:{case_id}".encode()).hexdigest()


def prepare_review(
    cases: list[EvalCase],
    online_report: dict[str, Any],
    artifacts_dir: Path,
    *,
    sample_rate: float = 0.2,
    seed: str = "eduflow-human-review-v1",
) -> dict[str, Any]:
    """Create a deterministic candidate/Judge-blinded review payload."""
    if not 0 < sample_rate <= 1:
        raise ValueError("sample_rate must be in (0, 1]")
    results = _result_map(online_report)
    case_ids = {case.case_id for case in cases}
    if set(results) != case_ids:
        missing = sorted(case_ids - set(results))
        extra = sorted(set(results) - case_ids)
        raise ValueError(f"report/dataset mismatch: missing={missing}, extra={extra}")

    eligible: list[tuple[EvalCase, dict[str, Any]]] = []
    for case in cases:
        result = results[case.case_id]
        if not isinstance(result.get("judge"), dict):
            raise TypeError(f"case has no independent Judge result: {case.case_id}")
        artifact_path = artifacts_dir / f"{case.case_id}.json"
        if not artifact_path.is_file():
            raise ValueError(f"case artifact is missing: {case.case_id}")
        artifact = _read_json(artifact_path)
        eligible.append((case, artifact))

    sample_count = max(1, math.ceil(len(eligible) * sample_rate))
    selected = sorted(
        eligible, key=lambda item: _sample_key(seed, item[0].case_id)
    )[:sample_count]
    reviews = []
    for case, artifact in selected:
        reviews.append(
            {
                "review_id": hashlib.sha256(
                    f"review:{seed}:{case.case_id}".encode()
                ).hexdigest()[:16],
                "case_id": case.case_id,
                "case": case.model_dump(mode="json", exclude={"tools", "retrieval"}),
                "artifact": artifact,
                "rubric": list(JUDGE_CRITERIA),
                "human_scores": {criterion: None for criterion in JUDGE_CRITERIA},
                "overall_score": None,
                "notes": "",
            }
        )
    return {
        "schema_version": "1.0",
        "blind": True,
        "selection": {
            "method": "sha256_seeded",
            "seed": seed,
            "population_size": len(eligible),
            "sample_size": sample_count,
            "sample_rate": round(sample_count / len(eligible), 4),
        },
        "reviews": reviews,
    }


def _validated_score(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
        raise ValueError(f"{field} must be an integer from 1 to 5")
    return value


def score_review(
    review_sheet: dict[str, Any],
    online_report: dict[str, Any],
    *,
    min_rate: float = 0.2,
) -> dict[str, Any]:
    """Validate completed labels and compare them with hidden Judge scores."""
    if not 0 < min_rate <= 1:
        raise ValueError("min_rate must be in (0, 1]")
    results = _result_map(online_report)
    reviews = review_sheet.get("reviews")
    if not isinstance(reviews, list) or not reviews:
        raise ValueError("review sheet contains no reviews")
    required_count = math.ceil(len(results) * min_rate)
    if len(reviews) < required_count:
        raise ValueError(
            f"review coverage below minimum: {len(reviews)}/{len(results)} < {min_rate:.0%}"
        )

    seen: set[str] = set()
    human_by_criterion: dict[str, list[int]] = {
        criterion: [] for criterion in JUDGE_CRITERIA
    }
    judge_by_criterion: dict[str, list[int]] = {
        criterion: [] for criterion in JUDGE_CRITERIA
    }
    human_overall: list[int] = []
    judge_overall: list[int] = []
    judge_models: set[str] = set()

    for review in reviews:
        if not isinstance(review, dict):
            raise TypeError("review entries must be objects")
        case_id = review.get("case_id")
        if not isinstance(case_id, str) or case_id in seen or case_id not in results:
            raise ValueError(f"invalid or duplicate reviewed case: {case_id}")
        seen.add(case_id)
        judge = results[case_id].get("judge")
        if not isinstance(judge, dict):
            raise TypeError(f"case has no Judge result: {case_id}")
        criteria = judge.get("criteria")
        human_scores = review.get("human_scores")
        if not isinstance(criteria, dict) or not isinstance(human_scores, dict):
            raise TypeError(f"case has incomplete rubric data: {case_id}")
        if set(human_scores) != set(JUDGE_CRITERIA):
            raise ValueError(f"human rubric mismatch: {case_id}")
        for criterion in JUDGE_CRITERIA:
            judge_item = criteria.get(criterion)
            if not isinstance(judge_item, dict):
                raise TypeError(f"Judge rubric mismatch: {case_id}/{criterion}")
            human_by_criterion[criterion].append(
                _validated_score(
                    human_scores[criterion], field=f"{case_id}/{criterion}"
                )
            )
            judge_by_criterion[criterion].append(
                _validated_score(
                    judge_item.get("score"), field=f"Judge {case_id}/{criterion}"
                )
            )
        human_overall.append(
            _validated_score(review.get("overall_score"), field=f"{case_id}/overall")
        )
        judge_overall.append(
            _validated_score(judge.get("overall_score"), field=f"Judge {case_id}/overall")
        )
        if isinstance(judge.get("judge_model"), str):
            judge_models.add(judge["judge_model"])

    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "population_size": len(results),
        "reviewed_count": len(reviews),
        "review_rate": round(len(reviews) / len(results), 4),
        "minimum_review_rate": min_rate,
        "judge_models": sorted(judge_models),
        "overall": calibration_report(human_overall, judge_overall),
        "criteria": {
            criterion: calibration_report(
                human_by_criterion[criterion], judge_by_criterion[criterion]
            )
            for criterion in JUDGE_CRITERIA
        },
        "reviewed_case_ids": sorted(seen),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--dataset", type=Path, required=True)
    prepare.add_argument("--report", type=Path, required=True)
    prepare.add_argument("--artifacts-dir", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--sample-rate", type=float, default=0.2)
    prepare.add_argument("--seed", default="eduflow-human-review-v1")
    score = subparsers.add_parser("score")
    score.add_argument("--review", type=Path, required=True)
    score.add_argument("--report", type=Path, required=True)
    score.add_argument("--output", type=Path, required=True)
    score.add_argument("--min-rate", type=float, default=0.2)
    args = parser.parse_args()

    if args.command == "prepare":
        payload = prepare_review(
            load_cases(args.dataset),
            _read_json(args.report),
            args.artifacts_dir,
            sample_rate=args.sample_rate,
            seed=args.seed,
        )
    else:
        payload = score_review(
            _read_json(args.review),
            _read_json(args.report),
            min_rate=args.min_rate,
        )
    _write_json(args.output, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
