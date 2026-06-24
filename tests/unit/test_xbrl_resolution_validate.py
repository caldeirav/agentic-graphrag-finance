"""Unit tests for post-selection XBRL resolution validation (023 M3)."""

from __future__ import annotations

from datetime import date

from retrieval.skills.metric_intent import MetricIntent
from retrieval.skills.temporal_scope import TemporalScopeIntent
from retrieval.skills.xbrl_fact_catalog import XbrlFactCatalogEntry
from retrieval.skills.xbrl_fact_resolution import XbrlFactResolutionResult
from retrieval.skills.xbrl_resolution_validate import validate_xbrl_resolution
from retrieval.skills.xbrl_taxonomy_catalog import enrich_catalog_entry


def _margin_catalog() -> list:
    return [
        enrich_catalog_entry(
            XbrlFactCatalogEntry(
                chunk_id="ni",
                concept="ProfitLoss",
                value_display="$29.76 billion",
                period_end="2025-12-31",
                is_annual=True,
            )
        ),
        enrich_catalog_entry(
            XbrlFactCatalogEntry(
                chunk_id="pretax",
                concept="IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
                value_display="$36.55 billion",
                period_end="2025-12-31",
                is_annual=True,
            )
        ),
        enrich_catalog_entry(
            XbrlFactCatalogEntry(
                chunk_id="rev",
                concept="TotalRevenuesAndOtherIncome",
                value_display="$326.00 billion",
                period_end="2025-12-31",
                is_annual=True,
            )
        ),
    ]


def test_validator_rejects_pretax_margin_numerator() -> None:
    intent = MetricIntent(metric_type="ratio", metric_label="Net profit margin", periods_needed=1)
    resolution = XbrlFactResolutionResult(
        selected_chunk_ids=["pretax", "rev"],
        sufficient=True,
        rationale="Picked pretax over net income.",
    )
    validated = validate_xbrl_resolution(
        resolution,
        _margin_catalog(),
        "What was net profit margin for fiscal year 2025?",
        metric_intent=intent,
    )
    assert validated.validation_rejections
    assert validated.resolution.sufficient is False
    assert any("pretax" in reason.lower() for reason in validated.validation_rejections)


def test_validator_accepts_net_income_margin_pair() -> None:
    intent = MetricIntent(metric_type="ratio", metric_label="Net profit margin", periods_needed=1)
    resolution = XbrlFactResolutionResult(
        selected_chunk_ids=["ni", "rev"],
        sufficient=True,
    )
    validated = validate_xbrl_resolution(
        resolution,
        _margin_catalog(),
        "What was net profit margin for fiscal year 2025?",
        metric_intent=intent,
    )
    assert validated.validation_rejections == []
    assert validated.resolution.sufficient is True
    assert validated.selected_concepts == ["ProfitLoss", "TotalRevenuesAndOtherIncome"]


def test_validator_rejects_equity_other_for_equity_query() -> None:
    catalog = [
        enrich_catalog_entry(
            XbrlFactCatalogEntry(
                chunk_id="other",
                concept="StockholdersEquityOther",
                value_display="$664.00 million",
                period_end="2026-04-01",
                is_annual=False,
            )
        )
    ]
    resolution = XbrlFactResolutionResult(
        selected_chunk_ids=["other"],
        sufficient=True,
    )
    validated = validate_xbrl_resolution(
        resolution,
        catalog,
        "What was total shareholder equity for fiscal year 2025?",
        metric_intent=MetricIntent(metric_type="point", metric_label="Total equity", periods_needed=1),
        temporal_intent=TemporalScopeIntent(
            target_fiscal_year=2025,
            form_preference="10-K",
        ),
    )
    assert validated.resolution.sufficient is False
    assert validated.validation_rejections


def test_validator_rejects_mismatched_ratio_periods() -> None:
    catalog = [
        enrich_catalog_entry(
            XbrlFactCatalogEntry(
                chunk_id="ni",
                concept="ProfitLoss",
                period_end="2025-12-31",
                is_annual=True,
            )
        ),
        enrich_catalog_entry(
            XbrlFactCatalogEntry(
                chunk_id="rev",
                concept="Revenues",
                period_end="2025-03-31",
                is_annual=False,
            )
        ),
    ]
    intent = MetricIntent(metric_type="ratio", metric_label="margin", periods_needed=1)
    resolution = XbrlFactResolutionResult(
        selected_chunk_ids=["ni", "rev"],
        sufficient=True,
    )
    validated = validate_xbrl_resolution(
        resolution,
        catalog,
        "Net profit margin FY2025",
        metric_intent=intent,
    )
    assert validated.resolution.sufficient is False
    assert any("different periods" in r for r in validated.validation_rejections)
