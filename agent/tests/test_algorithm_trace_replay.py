from __future__ import annotations

import asyncio
import json
from pathlib import Path

from evals.graders.deterministic import grade_artifact
from evals.models import EvalCase, EvalExpectation
from tools.algorithm_trace_compiler import compile_algorithm_trace
from tools.normalize_dsl import normalize_dsl
from tools.validate_dsl import stabilize_algorithm_trace

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "algorithm_replays"


def _case(case_id: str, topic: str, concepts: list[str]) -> EvalCase:
    return EvalCase(
        case_id=case_id,
        version="replay",
        domain="algorithm",
        difficulty="beginner",
        topic=topic,
        expected=EvalExpectation(
            required_concepts=concepts,
            min_frames=3,
            max_frames=8,
        ),
    )


def _replay(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_replay_failed_bfs_artifact_after_graph_normalization_and_compilation():
    raw = _replay("bfs_failed_artifact.json")
    artifact = compile_algorithm_trace(
        stabilize_algorithm_trace(normalize_dsl(raw))
    )

    result = asyncio.run(
        grade_artifact(
            _case(
                "replay-bfs",
                raw["topic"],
                ["队列", "FIFO", "逐层访问"],
            ),
            artifact,
        )
    )

    assert result["passed"] is True, result["issues"]
    assert artifact["algorithm_trace_compilation"]["issues"] == []
    assert artifact["frames"][-1]["state_snapshot"]["visited"] == [
        "node-s", "node-a", "node-b", "node-c", "node-d"
    ]


def test_replay_failed_bellman_ford_artifact_after_edge_scan_normalization():
    raw = _replay("bellman_ford_failed_artifact.json")
    artifact = compile_algorithm_trace(
        stabilize_algorithm_trace(normalize_dsl(raw))
    )

    result = asyncio.run(
        grade_artifact(
            _case(
                "replay-bellman-ford",
                raw["topic"],
                ["负权边", "松弛", "负环"],
            ),
            artifact,
        )
    )

    assert result["passed"] is True, result["issues"]
    assert artifact["algorithm_trace_compilation"]["issues"] == []
    assert artifact["frames"][0]["state_snapshot"]["queue"] == []
    assert artifact["frames"][0]["state_snapshot"]["edge_scan"] == [
        {"source": "node-s", "target": "node-a", "weight": 4},
        {"source": "node-a", "target": "node-b", "weight": -2},
    ]
