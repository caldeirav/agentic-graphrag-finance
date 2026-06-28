"""Unit tests for segment-aware XBRL catalog (022-E / 023 M3)."""

from __future__ import annotations

from datetime import date

from models.enums import EvidenceSourceType
from models.filing import FilingRef
from models.query import EvidenceChunk
from retrieval.skills.metric_intent import MetricIntent
from retrieval.skills.xbrl_fact_catalog import build_xbrl_fact_catalog
from retrieval.skills.xbrl_fact_resolution import XbrlFactResolutionResult
from retrieval.skills.xbrl_resolution_validate import validate_xbrl_resolution
from retrieval.skills.xbrl_taxonomy_catalog import enrich_catalog_entry


def _chunk(chunk_id: str, excerpt: str) -> EvidenceChunk:
    return EvidenceChunk(
        chunk_node_id=chunk_id,
        excerpt=excerpt,
        content_hash="h",
        citation_label="XBRL",
        source_type=EvidenceSourceType.XBRL,
        section_id="XBRL",
    )


def test_segment_catalog_includes_consolidated_and_segment_rows_live() -> None:
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
    query = "What was Energy Products segment revenue for fiscal year 2025?"
    metric = MetricIntent(metric_type="point", metric_label="segment revenue", periods_needed=1)
    catalog = build_xbrl_fact_catalog(
        evidence,
        query,
        [filing],
        metric_intent=metric,
        strict_concept=False,
    )
    assert len(catalog) == 2
    segment_rows = [
        e for e in catalog if "Energy Products" in (e.segment_hint or e.segment_dimension or "")
    ]
    assert len(segment_rows) == 1
    assert segment_rows[0].chunk_id == "segment"


def test_validator_rejects_consolidated_revenue_for_segment_query() -> None:
    catalog = [
        enrich_catalog_entry(
            build_xbrl_fact_catalog(
                [
                    _chunk(
                        "consolidated",
                        "XBRL Revenues: $413.00 billion USD for period 2025-01-01 - 2025-12-31",
                    )
                ],
                "What was Energy Products segment revenue for fiscal year 2025?",
                [],
                metric_intent=MetricIntent(
                    metric_type="point",
                    metric_label="segment revenue",
                    periods_needed=1,
                ),
                strict_concept=False,
            )[0]
        )
    ]
    validated = validate_xbrl_resolution(
        XbrlFactResolutionResult(selected_chunk_ids=["consolidated"], sufficient=True),
        catalog,
        "What was Energy Products segment revenue for fiscal year 2025?",
        metric_intent=MetricIntent(
            metric_type="point",
            metric_label="segment revenue",
            periods_needed=1,
        ),
    )
    assert validated.resolution.sufficient is False
