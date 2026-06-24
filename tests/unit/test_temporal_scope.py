"""Unit tests for temporal scope intent (021)."""

from __future__ import annotations

from retrieval.macro.pairing import annual_fiscal_year_requested, detect_quarterly_metric_cue
from retrieval.skills.temporal_scope import infer_temporal_scope_intent


def test_annual_fiscal_year_disables_quarterly_cue() -> None:
    q = "What was revenue for fiscal year 2025?"
    assert annual_fiscal_year_requested(q) is True
    assert detect_quarterly_metric_cue(q) is False


def test_infer_temporal_scope_prefers_fy10k() -> None:
    intent = infer_temporal_scope_intent(
        "What was Exxon Mobil total equity for fiscal year 2025?",
        fiscal_period_labels=["FY2025"],
    )
    assert intent.form_preference == "10-K"
    assert intent.target_fiscal_year == 2025
    assert "FY2025" in intent.period_labels


def test_quarter_query_prefers_10q() -> None:
    intent = infer_temporal_scope_intent("What was revenue in Q1 2025?")
    assert intent.form_preference == "10-Q"


def test_yoy_sets_comparison_mode() -> None:
    intent = infer_temporal_scope_intent(
        "How did net sales change year over year for fiscal year 2025?"
    )
    assert intent.comparison_mode == "yoy"
