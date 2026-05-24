"""Gold-path reachability metrics (009)."""

from __future__ import annotations


def chunk_reach_rate(results: list[dict]) -> float:
    if not results:
        return 0.0
    hits = sum(1 for r in results if r.get("reached"))
    return hits / len(results)


def path_match_rate(results: list[dict]) -> float:
    reached = [r for r in results if r.get("reached")]
    if not reached:
        return 0.0
    matched = sum(1 for r in reached if r.get("path_matched"))
    return matched / len(reached)


def is_full_graph_scan(scan_ratio: float, *, threshold: float = 0.90) -> bool:
    return scan_ratio >= threshold


def sequence_matches_pattern(
    sequence: list[str],
    patterns: list[list[str]],
) -> bool:
    """True if any acceptable pattern is a subsequence of *sequence*."""
    if not patterns:
        return True
    for pattern in patterns:
        if not pattern:
            continue
        idx = 0
        for edge in sequence:
            if idx < len(pattern) and edge == pattern[idx]:
                idx += 1
        if idx == len(pattern):
            return True
    return False
