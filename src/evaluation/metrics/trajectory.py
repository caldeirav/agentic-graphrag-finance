"""Trajectory fidelity aggregation."""

from __future__ import annotations

from models.query import TrajectoryRecord


def structural_overlap(
    visited_section_ids: list[str],
    expected_section_ids: list[str],
) -> float:
    if not expected_section_ids:
        return 1.0
    visited = set(visited_section_ids)
    expected = set(expected_section_ids)
    if not expected:
        return 0.0
    return len(visited & expected) / len(expected)


def trajectory_fidelity_score(
    trajectory: TrajectoryRecord,
    expected_section_ids: list[str] | None = None,
    judge_score: float | None = None,
) -> float:
    visited = [v.node_id for v in trajectory.graph_traversal]
    structural = structural_overlap(visited, expected_section_ids or [])
    router_bonus = 0.0
    if trajectory.intent_router is not None:
        router_bonus = 0.1
    base = min(1.0, structural + router_bonus)
    if judge_score is not None:
        return 0.5 * base + 0.5 * judge_score
    return base
