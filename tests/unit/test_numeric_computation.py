"""Unit tests for numeric computation (021)."""

from __future__ import annotations

from retrieval.skills.metric_intent import MetricIntent
from retrieval.skills.numeric_computation import compute_numeric_answer, parse_display_value
from retrieval.skills.temporal_scope import infer_temporal_scope_intent
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


def test_compute_ratio_outputs_percent_only() -> None:
    catalog = [
        XbrlFactCatalogEntry(
            chunk_id="tax",
            concept="IncomeTaxExpense",
            value_display="$8.67 billion",
            period_end="2025-12-31",
            is_annual=True,
            matches_query=True,
        ),
        XbrlFactCatalogEntry(
            chunk_id="pretax",
            concept="IncomeBeforeIncomeTaxes",
            value_display="$40.00 billion",
            period_end="2025-12-31",
            is_annual=True,
            matches_query=True,
        ),
    ]
    intent = MetricIntent(metric_type="ratio", metric_label="Effective tax rate", periods_needed=1)
    resolution = XbrlFactResolutionResult(
        selected_chunk_ids=["tax", "pretax"],
        sufficient=True,
    )
    payload = compute_numeric_answer(
        intent,
        resolution,
        catalog,
        query="What was the effective tax rate for fiscal year 2025?",
    )
    assert payload is not None
    assert payload.abstain is False
    assert payload.value.endswith("%")
    assert "$" not in payload.value


def test_compute_abstains_when_period_guard_fails() -> None:
    intent = MetricIntent(metric_type="point", metric_label="Equity", periods_needed=1)
    temporal = infer_temporal_scope_intent(
        "What was total shareholder equity for fiscal year 2025?",
        fiscal_period_labels=["FY2025"],
    )
    catalog = [
        XbrlFactCatalogEntry(
            chunk_id="bad",
            concept="StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
            value_display="$100.00 billion",
            period_start="2026-01-01",
            period_end="2026-04-01",
            is_annual=False,
            matches_query=True,
        )
    ]
    resolution = XbrlFactResolutionResult(selected_chunk_ids=["bad"], sufficient=True)
    payload = compute_numeric_answer(
        intent,
        resolution,
        catalog,
        query="What was total shareholder equity for fiscal year 2025?",
        temporal_intent=temporal,
    )
    assert payload is not None
    assert payload.abstain is True
