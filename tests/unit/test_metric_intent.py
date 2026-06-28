"""Unit tests for metric intent (021)."""

from __future__ import annotations

import os

from retrieval.skills.metric_intent import classify_metric_intent


def test_heuristic_percent_change(monkeypatch) -> None:
    monkeypatch.setenv("USE_MOCK_LLM", "1")
    intent, _ = classify_metric_intent(
        "What was the year-over-year percentage change in net income?"
    )
    assert intent.metric_type == "percent_change"
    assert intent.periods_needed == 2


def test_heuristic_ratio(monkeypatch) -> None:
    monkeypatch.setenv("USE_MOCK_LLM", "1")
    intent, _ = classify_metric_intent("What was the net profit margin for fiscal year 2025?")
    assert intent.metric_type == "ratio"
