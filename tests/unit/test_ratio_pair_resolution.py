"""Unit tests for ratio pair resolution (022-A)."""

from __future__ import annotations

from retrieval.skills.metric_intent import MetricIntent
from retrieval.skills.ratio_pair_resolution import infer_ratio_pair_intent, resolve_ratio_pair
from retrieval.skills.temporal_scope import infer_temporal_scope_intent
from retrieval.skills.xbrl_fact_catalog import XbrlFactCatalogEntry


def _entry(chunk_id: str, concept: str, value: str, period_end: str = "2025-12-31") -> XbrlFactCatalogEntry:
    return XbrlFactCatalogEntry(
        chunk_id=chunk_id,
        concept=concept,
        value_display=value,
        period_start="2025-01-01",
        period_end=period_end,
        is_annual=True,
        matches_query=True,
    )


def test_infer_margin_intent() -> None:
    intent = MetricIntent(metric_type="ratio", metric_label="margin", periods_needed=1)
    pair = infer_ratio_pair_intent(intent, "What was net profit margin for fiscal year 2025?")
    assert pair is not None
    assert pair.kind == "margin"


def test_resolve_margin_pair() -> None:
    catalog = [
        _entry("ni", "NetIncomeLoss", "$36.00 billion"),
        _entry("rev", "Revenues", "$413.00 billion"),
        _entry("tax", "IncomeTaxExpense", "$8.00 billion"),
    ]
    intent = MetricIntent(metric_type="ratio", metric_label="Net profit margin FY2025", periods_needed=1)
    temporal = infer_temporal_scope_intent("Net profit margin fiscal year 2025", fiscal_period_labels=["FY2025"])
    pair = resolve_ratio_pair(catalog, intent, "Net profit margin fiscal year 2025", temporal_intent=temporal)
    assert pair.sufficient
    assert pair.numerator_entry is not None
    assert pair.denominator_entry is not None
    assert "NetIncome" in pair.numerator_entry.concept or "Income" in pair.numerator_entry.concept
    assert "Revenue" in pair.denominator_entry.concept


def test_resolve_tax_rate_pair() -> None:
    catalog = [
        _entry("tax", "IncomeTaxExpense", "$8.67 billion"),
        _entry("pretax", "IncomeBeforeIncomeTaxes", "$40.00 billion"),
    ]
    intent = MetricIntent(metric_type="ratio", metric_label="Effective tax rate", periods_needed=1)
    pair = resolve_ratio_pair(catalog, intent, "What was the effective tax rate for fiscal year 2025?")
    assert pair.sufficient


def test_resolve_payout_pair() -> None:
    catalog = [
        _entry("div", "DividendsPaid", "$16.00 billion"),
        _entry("ni", "NetIncomeLoss", "$36.00 billion"),
    ]
    intent = MetricIntent(metric_type="ratio", metric_label="Dividend payout ratio", periods_needed=1)
    pair = resolve_ratio_pair(catalog, intent, "What was the dividend payout ratio for fiscal year 2025?")
    assert pair.sufficient


def test_single_fact_abstains() -> None:
    catalog = [_entry("ni", "NetIncomeLoss", "$36.00 billion")]
    intent = MetricIntent(metric_type="ratio", metric_label="margin", periods_needed=1)
    pair = resolve_ratio_pair(catalog, intent, "Net profit margin fiscal year 2025")
    assert not pair.sufficient
