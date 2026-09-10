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

    # Renderer-specific fields (for example ``current``, ``terminated`` and
    # ``shortest_path_tree``) live beside the executable algorithm state.  They
    # are not part of the core protocol, but dropping them would break the
    # teaching presentation.  Legacy aliases are still rejected explicitly by
    # ``validate_algorithm_snapshot`` below.
    model_config = ConfigDict(extra="allow")


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


def validate_algorithm_snapshot(snapshot: Any) -> list[str]:
    """Validate the canonical representation without judging algorithm truth."""
    if not isinstance(snapshot, dict) or snapshot.get("schema_version") is None:
        return []
    errors: list[str] = []
    try:
        AlgorithmState.model_validate(snapshot)
    except Exception as exc:  # pragma: no cover - pydantic formats nested errors
        errors.append(str(exc))
    aliases = {"priority_queue", "heap", "unvisited", "distances", "processed"}
    present = sorted(alias for alias in aliases if alias in snapshot)
    if present:
        errors.append(f"algorithm-trace-v1 forbids legacy aliases: {present}")
    queue = snapshot.get("queue")
    if not isinstance(queue, list):
        errors.append("algorithm-trace-v1 queue must be an array")
    else:
        for index, entry in enumerate(queue):
            if not isinstance(entry, dict) or not isinstance(entry.get("vertex"), str):
                errors.append(f"algorithm-trace-v1 queue[{index}] must contain string vertex")
            elif "priority" not in entry:
                errors.append(f"algorithm-trace-v1 queue[{index}] missing priority")
    return errors


__all__ = [
    "AlgorithmEvent",
    "AlgorithmName",
    "AlgorithmPhase",
    "AlgorithmState",
    "QueueEntry",
    "is_algorithm_snapshot",
    "validate_algorithm_snapshot",
]
