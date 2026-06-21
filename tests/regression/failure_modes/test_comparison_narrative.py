"""Regression: comparison narrative contrast (019 M4)."""

from __future__ import annotations

from evaluation.generation.comparison_gt import _CROSS_VERB


def test_cross_verb_pattern_matches_contrast_language() -> None:
    assert _CROSS_VERB.search("Company A increased while Company B decreased")
    assert not _CROSS_VERB.search("Company A reported revenue of $1B")
