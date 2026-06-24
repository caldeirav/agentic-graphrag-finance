"""Unit tests for numeric computation (021)."""

from __future__ import annotations

from retrieval.skills.metric_intent import MetricIntent
from retrieval.skills.numeric_computation import compute_numeric_answer, parse_display_value
from retrieval.skills.xbrl_fact_catalog import XbrlFactCatalogEntry
from retrieval.skills.xbrl_fact_resolution import XbrlFactResolutionResult


def test_parse_display_value_billion() -> None:
    assert parse_display_value("$416.16 billion") == 416_160_000_000


def test_compute_percent_change() -> None:
    catalog = [
        XbrlFactCatalogEntry(
            chunk_id="new",
            concept="NetIncome",
            value_display="$110.00 billion",
            period_end="2025-12-31",
            is_annual=True,
            matches_query=True,
        ),
        XbrlFactCatalogEntry(
            chunk_id="old",
            concept="NetIncome",
            value_display="$100.00 billion",
            period_end="2024-12-31",
            is_annual=True,
            matches_query=True,
        ),
    ]
    resolution = XbrlFactResolutionResult(
        selected_chunk_ids=["new", "old"],
        sufficient=True,
    )
    intent = MetricIntent(metric_type="percent_change", metric_label="YoY change", periods_needed=2)
    payload = compute_numeric_answer(intent, resolution, catalog)
    assert payload is not None
    assert payload.abstain is False
    assert "10.00%" in payload.value
