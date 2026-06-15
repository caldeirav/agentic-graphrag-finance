"""Selective benchmark expected_section_paths injection for repaired bundles."""

from __future__ import annotations

from evaluation.generation.path_sanitize import is_corrupt_section_path

_SAFE_INJECTION_MARKERS = (
    "md_and_a",
    "mda",
    "management",
    "discussion",
    "10-q",
    "10 q",
    "item 7",
    "sec-0",
    "xbrl",
    "financial facts",
)

_HARMFUL_INJECTION_MARKERS = (
    "business_description",
    "item 1. business",
    "item 1 business",
    "item_1",
)


def is_safe_benchmark_injection_path(path: str) -> bool:
    """True when a benchmark path should be injected even with suppression enabled."""
    if "/" not in path:
        return False
    if is_corrupt_section_path(path):
        return False
    tail = path.split("/", 1)[1].lower()
    norm = tail.replace("_", " ").replace("-", " ")
    if any(m in norm for m in _HARMFUL_INJECTION_MARKERS):
        if not any(m in norm for m in ("md_and_a", "mda", "management", "discussion")):
            return False
    return any(m in norm for m in _SAFE_INJECTION_MARKERS) or not any(
        m in norm for m in _HARMFUL_INJECTION_MARKERS
    )


def filter_benchmark_injection_paths(
    paths: list,
    *,
    suppress_benchmark_path_injection: bool,
) -> list[str]:
    """Return paths eligible for meso injection."""
    valid = [p for p in paths if isinstance(p, str) and "/" in p]
    if not suppress_benchmark_path_injection:
        return valid
    return [p for p in valid if is_safe_benchmark_injection_path(p)]
