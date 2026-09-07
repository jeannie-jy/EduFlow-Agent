"""EduFlowBench dataset and deterministic grader tests."""

from pathlib import Path

import pytest
from evals.graders import grade_artifact
from evals.graders.human_calibration import calibration_report
from evals.graders.llm_judge import (
    JUDGE_CRITERIA,
    CriterionScore,
    JudgeResult,
    build_judge_request,
    merge_judge_with_deterministic,
)
from evals.graders.retrieval import grade_retrieval
from evals.models import EvalCase, load_cases
from evals.runners.compare_runs import compare_reports
from evals.runners.run_offline import run_dataset
from evals.runners.run_online import _report_exit_code, run_online_cases

DATASET = Path(__file__).parents[1] / "evals" / "datasets" / "eduflowbench_v1.jsonl"
INJECTION_DATASET = DATASET.with_name("injection_cases.jsonl")
RETRIEVAL_DATASET = DATASET.with_name("retrieval_cases.jsonl")
TOOL_ONLINE_DATASET = DATASET.with_name("tool_online_cases.jsonl")
CASE_SCHEMA = DATASET.parents[1] / "schemas" / "case.schema.json"


def _case(**expected_overrides) -> EvalCase:
    expected = {
        "required_concepts": ["冒泡排序"],
        "forbidden_claims": ["Dijkstra"],
        "min_frames": 1,
        "max_frames": 5,
        **expected_overrides,
    }
    return EvalCase.model_validate({
        "case_id": "alg_bubble_test",
        "domain": "algorithm",
        "difficulty": "beginner",
        "topic": "冒泡排序",
        "expected": expected,
        "oracle": {
            "kind": "sorted_array",
            "input": {"values": [3, 1, 2]},
            "expected": [1, 2, 3],
        },
    })


def _artifact() -> dict:
    return {
        "project_id": "eval",
        "topic": "冒泡排序",
        "frames": [{
            "frame_id": "f_001",
            "title": "冒泡排序完成",
            "narration": "通过相邻元素比较和交换完成排序",
            "visual_objects": [{
                "id": "arr",
                "type": "array",
                "cells": [
                    {"index": 0, "value": 1},
                    {"index": 1, "value": 2},
                    {"index": 2, "value": 3},
                ],
            }],
            "state_snapshot": {"array": [1, 2, 3]},
        }],
    }


def test_v1_dataset_has_unique_fifty_case_baseline():
    cases = load_cases(DATASET)
    assert len(cases) == 50
    assert len({case.case_id for case in cases}) == 50
    assert {case.domain for case in cases} >= {
        "algorithm", "data_structure", "operating_system", "network", "database", "custom"
    }


def test_robustness_and_retrieval_datasets_are_versioned_and_typed():
    injection = load_cases(INJECTION_DATASET)
    retrieval = load_cases(RETRIEVAL_DATASET)
    assert len(injection) >= 8
    assert all("prompt-injection" in case.tags for case in injection)
    assert len(retrieval) >= 10
    assert all(case.retrieval is not None for case in retrieval)
    assert __import__("json").loads(CASE_SCHEMA.read_text(encoding="utf-8"))["$schema"].endswith(
        "2020-12/schema"
    )


def test_online_tool_dataset_targets_real_registry_contract():
    cases = load_cases(TOOL_ONLINE_DATASET)
    assert len(cases) == 8
    assert all(case.tools is not None for case in cases)
    expected = {
        tool
        for case in cases
        if case.tools is not None
        for tool in case.tools.expected_tools
    }
    assert expected == {"knowledge_search", "material_lookup", "get_project_context"}


@pytest.mark.asyncio
async def test_deterministic_grader_accepts_valid_oracle_artifact():
    result = await grade_artifact(_case(), _artifact())
    assert result["passed"] is True
    assert result["metrics"]["dsl_schema_pass"] is True
    assert result["metrics"]["oracle_pass"] is True


@pytest.mark.asyncio
async def test_deterministic_grader_cannot_hide_blocking_failures():
    artifact = _artifact()
    artifact["frames"][-1]["state_snapshot"]["array"] = [3, 2, 1]
    artifact["frames"][-1]["narration"] += " Dijkstra"

    result = await grade_artifact(_case(), artifact)

    assert result["passed"] is False
    assert result["metrics"]["oracle_pass"] is False
    assert result["metrics"]["forbidden_claim_pass"] is False


@pytest.mark.asyncio
async def test_forbidden_claim_allows_explicit_negation():
    case = _case(
        required_concepts=["快速排序"],
        forbidden_claims=["稳定排序"],
    ).model_copy(update={"topic": "快速排序"})
    artifact = _artifact()
    artifact["topic"] = "快速排序"
    artifact["frames"][0]["narration"] = "快速排序不是稳定排序。"

    result = await grade_artifact(case, artifact)

    assert result["passed"] is True
    assert result["metrics"]["forbidden_claim_pass"] is True


@pytest.mark.asyncio
async def test_forbidden_claim_still_blocks_positive_assertion():
    case = _case(
        required_concepts=["快速排序"],
        forbidden_claims=["稳定排序"],
    ).model_copy(update={"topic": "快速排序"})
    artifact = _artifact()
    artifact["topic"] = "快速排序"
    artifact["frames"][0]["narration"] = "快速排序是稳定排序。"

    result = await grade_artifact(case, artifact)

    assert result["passed"] is False
    assert result["metrics"]["forbidden_claim_pass"] is False


@pytest.mark.asyncio
async def test_forbidden_claim_allows_multiple_choice_distractor():
    case = _case(
        required_concepts=["快速排序"],
        forbidden_claims=["稳定排序"],
    ).model_copy(update={"topic": "快速排序"})
    artifact = _artifact()
    artifact["topic"] = "快速排序"
    artifact["frames"][0]["narration"] = "快速排序的练习选项如下。"
    artifact["frames"][0]["state_snapshot"] = {
        "array": [1, 2, 3],
        "practice": {
            "question": "快速排序是否稳定？",
            "options": ["快速排序是稳定排序", "快速排序不是稳定排序"],
        }
    }

    result = await grade_artifact(case, artifact)

    assert result["passed"] is True
    assert result["metrics"]["forbidden_claim_pass"] is True


@pytest.mark.asyncio
async def test_sorted_array_oracle_accepts_explicit_result_key():
    artifact = _artifact()
    artifact["frames"][-1]["state_snapshot"] = {"sorted_array": [1, 2, 3]}

    result = await grade_artifact(_case(), artifact)

    assert result["passed"] is True
    assert result["metrics"]["oracle_pass"] is True


@pytest.mark.asyncio
async def test_duplicate_frame_ids_are_a_blocking_failure():
    artifact = _artifact()
    artifact["frames"].append(dict(artifact["frames"][0]))
    result = await grade_artifact(_case(max_frames=5), artifact)
    assert result["passed"] is False
    assert result["metrics"]["frame_id_uniqueness_pass"] is False


def test_retrieval_metrics_cover_ranking_and_invalid_citations():
    case = load_cases(RETRIEVAL_DATASET)[0]
    result = grade_retrieval(
        case,
        ["irrelevant", "algo-dijkstra-constraints"],
        ["algo-dijkstra-constraints", "invented-source"],
    )
    assert result["recall_at_k"] == 1.0
    assert result["mrr"] == 0.5
    assert result["citation_correctness"] == 0.5
    assert result["unknown_citations"] == ["invented-source"]


@pytest.mark.asyncio
async def test_runner_reports_missing_artifacts(tmp_path):
    cases = [_case(), _case().model_copy(update={"case_id": "alg_missing"})]
    (tmp_path / "alg_bubble_test.json").write_text(
        __import__("json").dumps(_artifact(), ensure_ascii=False),
        encoding="utf-8",
    )

    report = await run_dataset(cases, tmp_path)

    assert report["summary"]["evaluated_cases"] == 1
    assert report["summary"]["missing_artifacts"] == 1
    assert report["summary"]["pass_rate"] == 1.0
    assert report["run"]["git_sha"]


def test_compare_runs_blocks_quality_regression_and_warns_on_latency():
    baseline = {"summary": {"pass_rate": 1.0, "p95_latency_ms": 100}}
    candidate = {"summary": {"pass_rate": 0.95, "p95_latency_ms": 130}}
    comparison = compare_reports(baseline, candidate)
    assert comparison["passed"] is False
    assert comparison["failure_count"] == 1
    assert comparison["warning_count"] == 1


def test_judge_is_blinded_and_cannot_override_deterministic_failure():
    request = build_judge_request(_case().model_dump(), _artifact())
    assert "candidate_model" not in request
    judge = JudgeResult(
        case_id="alg_bubble_test",
        judge_model="independent-judge",
        criteria={
            name: CriterionScore(score=5, reason="meets rubric")
            for name in JUDGE_CRITERIA
        },
        overall_score=5,
        deterministic_passed=False,
    )
    merged = merge_judge_with_deterministic(
        {"case_id": "alg_bubble_test", "passed": False}, judge
    )
    assert merged["passed"] is False
    assert merged["semantic_score"] == 5


def test_human_calibration_reports_agreement():
    report = calibration_report([5, 4, 3, 2], [5, 4, 2, 2])
    assert report["sample_size"] == 4
    assert report["exact_agreement"] == 0.75
    assert report["within_one_agreement"] == 1.0


@pytest.mark.asyncio
async def test_online_runner_is_bounded_and_collects_engineering_metrics(tmp_path):
    active = 0
    peak = 0

    async def fake_generator(_case):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await __import__("asyncio").sleep(0.01)
        active -= 1
        return {
            "artifact": _artifact(),
            "usage": {"input": 10, "output": 20},
            "cost_usd": 0.01,
            "metadata": {"quality_report": {"overall_score": 0.8}},
        }

    cases = [
        _case().model_copy(update={"case_id": f"alg_online_{i}"})
        for i in range(4)
    ]
    report = await run_online_cases(
        cases, fake_generator, concurrency=2, artifacts_dir=tmp_path
    )
    assert peak == 2
    assert report["summary"]["passed_cases"] == 4
    assert report["summary"]["total_cost_usd"] == 0.04
    assert report["results"][0]["generator_metadata"]["quality_report"][
        "overall_score"
    ] == 0.8
    assert len(list(tmp_path.glob("*.json"))) == 4


@pytest.mark.asyncio
async def test_online_runner_excludes_semaphore_queue_wait_from_percentiles():
    async def slow_generator(_case):
        await __import__("asyncio").sleep(0.03)
        return {"artifact": _artifact(), "cost_usd": 0.01}

    cases = [
        _case().model_copy(update={"case_id": f"alg_timing_{index}"})
        for index in range(2)
    ]
    report = await run_online_cases(cases, slow_generator, budget_usd=1.0)
    first, second = report["results"]

    assert first["latency_ms"] == first["processing_latency_ms"]
    assert second["latency_ms"] == second["processing_latency_ms"]
    assert second["queue_wait_ms"] > 10
    assert second["wall_clock_latency_ms"] > second["processing_latency_ms"]
    assert report["summary"]["latency_basis"] == "processing_latency_ms"
    assert report["summary"]["p50_latency_ms"] <= report["summary"]["p95_latency_ms"]
    assert report["summary"]["wall_clock_p95_latency_ms"] >= report["summary"]["p95_latency_ms"]


def test_online_runner_exit_code_enforces_reported_cost_budget():
    report = {"summary": {"passed_cases": 1, "budget_exceeded": True}, "results": [{}]}
    assert _report_exit_code(report) == 1
    report["summary"]["budget_exceeded"] = False
    assert _report_exit_code(report) == 0


@pytest.mark.asyncio
async def test_online_runner_stops_starting_cases_after_cost_budget():
    calls: list[str] = []

    async def priced_generator(case):
        calls.append(case.case_id)
        return {"artifact": _artifact(), "cost_usd": 0.03}

    cases = [
        _case().model_copy(update={"case_id": f"alg_budget_{index}"})
        for index in range(3)
    ]
    report = await run_online_cases(
        cases,
        priced_generator,
        concurrency=3,
        budget_usd=0.02,
    )

    assert calls == ["alg_budget_0"]
    assert report["summary"]["budget_exceeded"] is True
    assert report["summary"]["total_cost_usd"] == 0.03
    assert report["results"][1]["issues"] == [
        "generation skipped: run cost budget exhausted"
    ]


@pytest.mark.asyncio
async def test_online_runner_rejects_non_positive_budget():
    async def generator(_case):
        raise AssertionError("invalid budget must fail before generation")

    with pytest.raises(ValueError, match="greater than zero"):
        await run_online_cases([_case()], generator, budget_usd=0)


@pytest.mark.asyncio
async def test_online_runner_merges_independent_judge_and_separates_costs():
    async def generator(_case):
        return {
            "artifact": _artifact(),
            "usage": {"input": 10, "output": 20},
            "cost_usd": 0.01,
        }

    async def judge(case, artifact, deterministic):
        assert artifact["topic"] == "冒泡排序"
        return {
            "judge": JudgeResult(
                case_id=case.case_id,
                judge_model="independent-model",
                criteria={
                    name: CriterionScore(score=4, reason="meets rubric")
                    for name in JUDGE_CRITERIA
                },
                overall_score=4,
                deterministic_passed=deterministic["passed"],
            ).model_dump(),
            "usage": {"input": 30, "output": 40},
            "cost_usd": 0.02,
        }

    report = await run_online_cases([_case()], generator, judge=judge)
    result = report["results"][0]

    assert result["passed"] is True
    assert result["semantic_score"] == 4
    assert result["candidate_cost_usd"] == 0.01
    assert result["judge_cost_usd"] == 0.02
    assert result["cost_usd"] == 0.03
    assert report["summary"]["total_cost_usd"] == 0.03


@pytest.mark.asyncio
async def test_online_runner_does_not_start_judge_after_candidate_exhausts_budget():
    judge_calls = 0

    async def generator(_case):
        return {"artifact": _artifact(), "cost_usd": 0.02}

    async def judge(*args):
        nonlocal judge_calls
        judge_calls += 1
        raise AssertionError(args)

    report = await run_online_cases(
        [_case()], generator, judge=judge, budget_usd=0.02
    )

    assert judge_calls == 0
    assert report["results"][0]["passed"] is False
    assert report["results"][0]["issues"][-1] == (
        "judge skipped: run cost budget exhausted"
    )
    assert report["summary"]["budget_exceeded"] is True


@pytest.mark.asyncio
async def test_online_runner_preserves_candidate_cost_when_judge_fails():
    async def generator(_case):
        return {
            "artifact": _artifact(),
            "usage": {"input": 10, "output": 20},
            "cost_usd": 0.01,
        }

    async def judge(*_args):
        raise TimeoutError("judge timeout")

    report = await run_online_cases([_case()], generator, judge=judge)
    result = report["results"][0]

    assert result["passed"] is False
    assert result["candidate_cost_usd"] == 0.01
    assert result["cost_usd"] == 0.01
    assert result["judge_error"] == "TimeoutError"
    assert result["issues"][-1] == "judge failed: TimeoutError: judge timeout"
    assert report["summary"]["total_cost_usd"] == 0.01
