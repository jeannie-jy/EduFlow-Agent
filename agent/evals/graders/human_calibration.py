"""Human-vs-judge calibration metrics for a reviewed EduFlowBench sample."""

from __future__ import annotations

from collections import Counter
from typing import Iterable


def calibration_report(
    human_scores: Iterable[int], judge_scores: Iterable[int]
) -> dict[str, float | int]:
    human = list(human_scores)
    judge = list(judge_scores)
    if not human or len(human) != len(judge):
        raise ValueError("human and judge scores must be non-empty and have equal length")
    if any(not isinstance(score, int) or score < 1 or score > 5 for score in human + judge):
        raise ValueError("all calibration scores must be integers from 1 to 5")

    pairs = list(zip(human, judge, strict=True))
    exact = sum(a == b for a, b in pairs) / len(human)
    within_one = sum(abs(a - b) <= 1 for a, b in pairs) / len(human)
    mean_absolute_error = sum(abs(a - b) for a, b in pairs) / len(human)

    human_counts = Counter(human)
    judge_counts = Counter(judge)
    expected = sum(
        (human_counts[value] / len(human)) * (judge_counts[value] / len(judge))
        for value in range(1, 6)
    )
    kappa = (exact - expected) / (1 - expected) if expected < 1 else 1.0
    return {
        "sample_size": len(human),
        "exact_agreement": round(exact, 4),
        "within_one_agreement": round(within_one, 4),
        "mean_absolute_error": round(mean_absolute_error, 4),
        "cohen_kappa": round(kappa, 4),
    }
