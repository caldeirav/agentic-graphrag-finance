"""Unit tests for point fact selection (022-B)."""

from __future__ import annotations

from datetime import date

from models.enums import EvidenceSourceType
from models.filing import FilingRef
from models.query import EvidenceChunk
from retrieval.skills.metric_intent import MetricIntent
from retrieval.skills.point_fact_selection import select_point_fact
from retrieval.skills.temporal_scope import infer_temporal_scope_intent
from retrieval.skills.xbrl_fact_catalog import XbrlFactCatalogEntry


def _chunk(chunk_id: str, excerpt: str, accession: str) -> EvidenceChunk:
    return EvidenceChunk(
        chunk_node_id=chunk_id,
        excerpt=excerpt,
        content_hash="h",
        citation_label="XBRL",
        source_type=EvidenceSourceType.XBRL,
        section_id="XBRL",
        accession=accession,
    )


def test_select_equity_annual() -> None:
    xom_acc = "0000034088-26-000045"
    cat_acc = "0000018230-26-000012"
    catalog = [
        XbrlFactCatalogEntry(
            chunk_id="q1",
            concept="StockholdersEquityOther",
            value_display="$664.00 million",
            period_end="2026-04-01",
            is_annual=False,
        ),
        XbrlFactCatalogEntry(
            chunk_id="fy",
            concept="StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
            value_display="$216.10 billion",
            period_end="2025-12-31",
            is_annual=True,
            matches_query=True,
        ),
        XbrlFactCatalogEntry(
            chunk_id="cat",
            concept="StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
            value_display="$18.00 billion",
            period_end="2025-12-31",
            is_annual=True,
            matches_query=True,
        ),
    ]
    evidence = [
        _chunk("fy", "XBRL equity", xom_acc),
        _chunk("cat", "XBRL equity", cat_acc),
    ]
    filing_set = [
        FilingRef(
            cik="34088",
            accession=xom_acc,
            form_type="10-K",
            filed_at=date(2026, 2, 1),
            period_end=date(2025, 12, 31),
            source_uri="",
        )
    ]
    intent = MetricIntent(metric_type="point", metric_label="equity", periods_needed=1)
    temporal = infer_temporal_scope_intent(
        "What was total shareholder equity for fiscal year 2025?",
        fiscal_period_labels=["FY2025"],
    )
    point = select_point_fact(
        catalog,
        "What was total shareholder equity for fiscal year 2025?",
        intent,
        temporal_intent=temporal,
        evidence=evidence,
        filing_set=filing_set,
    )
    assert point is not None
    assert point.chunk_id == "fy"
    assert "EquityOther" not in point.concept


def test_select_cash_prefers_primary_concept() -> None:
    catalog = [
        XbrlFactCatalogEntry(
            chunk_id="cash",
            concept="CashAndCashEquivalentsAtCarryingValue",
            value_display="$25.00 billion",
            period_end="2025-12-31",
            is_annual=True,
            matches_query=True,
        ),
        XbrlFactCatalogEntry(
            chunk_id="other",
            concept="CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
            value_display="$26.00 billion",
            period_end="2025-12-31",
            is_annual=True,
        ),
    ]
    intent = MetricIntent(metric_type="point", metric_label="cash", periods_needed=1)
    point = select_point_fact(catalog, "What was cash and cash equivalents FY2025?", intent)
    assert point is not None
    assert point.chunk_id == "cash"
