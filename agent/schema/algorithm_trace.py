"""Versioned algorithm-trace contract used by deterministic guardrails.

The general RenderScript ``state_snapshot`` remains intentionally extensible
for non-algorithm lessons.  Algorithm lessons opt into this contract so the
model may not invent competing queue/graph state encodings.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


AlgorithmName = Literal["dijkstra", "bellman_ford", "bfs", "dfs", "generic"]
AlgorithmPhase = Literal[
    "intro",
    "init",
    "select",
    "relax",
    "enqueue",
    "dequeue",
    "visit",
    "round",
    "summary",
    "negative_cycle_detection",
    "comparison",
    "custom",
]


class QueueEntry(BaseModel):
    """Canonical queue entry; ``priority`` is optional for FIFO/DFS traces."""

    vertex: str = Field(min_length=1, max_length=120)
    priority: float | int | str | None = None

    model_config = ConfigDict(extra="forbid")


class AlgorithmEvent(BaseModel):
    """Deterministic operation emitted by an algorithm-aware generator."""

    operation: Literal[
        "select",
        "relax",
        "enqueue",
        "dequeue",
        "visit",
        "detect_negative_cycle",
        "complete",
    ]
    source: str | None = None
    target: str | None = None
    weight: float | int | None = None
    value: float | int | str | None = None

    model_config = ConfigDict(extra="forbid")


class AlgorithmState(BaseModel):
    """Canonical state snapshot for algorithm lessons.

    The model can provide an optional ``events`` list while the compiler is
    migrated to derive state deterministically.  Existing generic snapshots
    are not forced through this model until they explicitly opt in with the
    version field.
    """

    schema_version: Literal["algorithm-trace-v1"]
    algorithm: AlgorithmName
    phase: AlgorithmPhase | str = "custom"
    dist: dict[str, float | int | str] = Field(default_factory=dict)
    visited: list[str] = Field(default_factory=list)
    queue: list[QueueEntry] = Field(default_factory=list)
    predecessor: dict[str, str | None] = Field(default_factory=dict)
    round: int | None = Field(default=None, ge=0)
    events: list[AlgorithmEvent] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


def is_algorithm_snapshot(snapshot: Any) -> bool:
    """Return whether a snapshot opts into or clearly represents this trace."""
    if not isinstance(snapshot, dict):
        return False
    if snapshot.get("schema_version") == "algorithm-trace-v1":
        return True
    return any(
        key in snapshot
        for key in (
            "algorithm",
            "dist",
            "distances",
            "visited",
            "processed",
            "queue",
            "priority_queue",
            "heap",
            "unvisited",
            "predecessor",
            "predecessors",
            "parents",
        )
    )


__all__ = [
    "AlgorithmEvent",
    "AlgorithmName",
    "AlgorithmPhase",
    "AlgorithmState",
    "QueueEntry",
    "is_algorithm_snapshot",
]
