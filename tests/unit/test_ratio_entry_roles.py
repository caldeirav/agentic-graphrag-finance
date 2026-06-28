"""Unit tests for role-aware ratio pair assignment (023 M4b)."""

from __future__ import annotations

from retrieval.skills.metric_intent import MetricIntent
from retrieval.skills.ratio_entry_roles import assign_ratio_pair_for_query
from retrieval.skills.xbrl_fact_catalog import XbrlFactCatalogEntry
from retrieval.skills.xbrl_taxonomy_catalog import enrich_catalog_entry


def test_assign_margin_pair_reversed_order() -> None:
    pretax = enrich_catalog_entry(
        XbrlFactCatalogEntry(
            chunk_id="pretax",
            concept="IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
            value_display="$48.87 billion",
            period_end="2025-12-31",
            is_annual=True,
        )
    )
    rev = enrich_catalog_entry(
        XbrlFactCatalogEntry(
            chunk_id="rev",
            concept="Revenues",
            value_display="$326.00 billion",
            period_end="2025-12-31",
            is_annual=True,
        )
    )
    intent = MetricIntent(metric_type="ratio", metric_label="Net profit margin", periods_needed=1)
    pair = assign_ratio_pair_for_query([rev, pretax], "Net profit margin FY2025", intent)
    assert pair is not None
    num, den = pair
    assert num.chunk_id == "pretax"
    assert den.chunk_id == "rev"


def test_assign_tax_rate_pair_reversed_order() -> None:
    tax = enrich_catalog_entry(
        XbrlFactCatalogEntry(
            chunk_id="tax",
            concept="IncomeTaxExpense",
            value_display="$8.67 billion",
            period_end="2025-12-31",
            is_annual=True,
        )
    )
    pretax = enrich_catalog_entry(
        XbrlFactCatalogEntry(
            chunk_id="pretax",
            concept="IncomeBeforeIncomeTaxes",
            value_display="$40.00 billion",
            period_end="2025-12-31",
            is_annual=True,
        )
    )
    intent = MetricIntent(metric_type="ratio", metric_label="Effective tax rate", periods_needed=1)
    pair = assign_ratio_pair_for_query([pretax, tax], "Effective tax rate FY2025", intent)
    assert pair is not None
    num, den = pair
    assert num.chunk_id == "tax"
    assert den.chunk_id == "pretax"
