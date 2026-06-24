"""Unit tests for segment-aware XBRL catalog (022-E)."""

from __future__ import annotations

from datetime import date

from models.enums import EvidenceSourceType
from models.filing import FilingRef
from models.query import EvidenceChunk
from retrieval.skills.metric_intent import MetricIntent
from retrieval.skills.xbrl_fact_catalog import build_xbrl_fact_catalog


def _chunk(chunk_id: str, excerpt: str) -> EvidenceChunk:
    return EvidenceChunk(
        chunk_node_id=chunk_id,
        excerpt=excerpt,
        content_hash="h",
        citation_label="XBRL",
        source_type=EvidenceSourceType.XBRL,
        section_id="XBRL",
    )


def test_segment_catalog_prefers_segment_revenue() -> None:
    filing = FilingRef(
        cik="34088",
        accession="acc",
        form_type="10-K",
        filed_at=date(2026, 1, 1),
        period_end=date(2025, 12, 31),
        source_uri="",
    )
    evidence = [
        _chunk(
            "consolidated",
            "XBRL Revenues: $413.00 billion USD for period 2025-01-01 - 2025-12-31",
        ),
        _chunk(
            "segment",
            "XBRL RevenueFromContractWithCustomerExcludingAssessedTax Energy Products segment: "
            "$254.00 billion USD for period 2025-01-01 - 2025-12-31",
        ),
    ]
    metric = MetricIntent(metric_type="point", metric_label="segment revenue", periods_needed=1)
    catalog = build_xbrl_fact_catalog(
        evidence,
        "What was Energy Products segment revenue for fiscal year 2025?",
        [filing],
        metric_intent=metric,
    )
    assert catalog
    assert all("Energy Products" in (e.segment_hint or e.segment_dimension or "") for e in catalog)
    assert all(e.chunk_id != "consolidated" for e in catalog)
