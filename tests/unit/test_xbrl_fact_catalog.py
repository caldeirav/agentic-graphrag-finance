"""Unit tests for XBRL fact catalog (021)."""

from __future__ import annotations

from datetime import date

from models.enums import EvidenceSourceType
from models.filing import FilingRef
from models.query import EvidenceChunk
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


def test_catalog_prefers_matching_concept_and_period() -> None:
    filing = FilingRef(
        cik="34088",
        accession="acc",
        form_type="10-K",
        filed_at=date(2025, 1, 1),
        period_end=date(2025, 12, 31),
        source_uri="",
    )
    evidence = [
        _chunk(
            "q1",
            "XBRL StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest: "
            "$269.81 billion USD for period 2025-01-01 - 2025-04-01",
        ),
        _chunk(
            "fy",
            "XBRL StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest: "
            "$216.10 billion USD for period 2025-01-01 - 2025-12-31",
        ),
    ]
    catalog = build_xbrl_fact_catalog(
        evidence,
        "What was total shareholder equity for fiscal year 2025?",
        [filing],
    )
    assert len(catalog) >= 1
    assert all("EquityOther" not in e.concept for e in catalog)
    annual = [e for e in catalog if e.is_annual]
    assert annual
    assert annual[0].chunk_id == "fy"


def test_catalog_excludes_equity_other_when_strict() -> None:
    filing = FilingRef(
        cik="34088",
        accession="acc",
        form_type="10-K",
        filed_at=date(2025, 1, 1),
        period_end=date(2025, 12, 31),
        source_uri="",
    )
    evidence = [
        _chunk(
            "other",
            "XBRL StockholdersEquityOther: $664.00 million USD for period 2026-01-01 - 2026-04-01",
        ),
    ]
    catalog = build_xbrl_fact_catalog(
        evidence,
        "What was total shareholder equity for fiscal year 2025?",
        [filing],
        strict_concept=True,
    )
    assert catalog == []


def test_live_catalog_includes_guarded_concepts_for_validator() -> None:
    filing = FilingRef(
        cik="34088",
        accession="acc",
        form_type="10-K",
        filed_at=date(2025, 1, 1),
        period_end=date(2025, 12, 31),
        source_uri="",
    )
    evidence = [
        _chunk(
            "other",
            "XBRL StockholdersEquityOther: $664.00 million USD for period 2026-01-01 - 2026-04-01",
        ),
    ]
    catalog = build_xbrl_fact_catalog(
        evidence,
        "What was total shareholder equity for fiscal year 2025?",
        [filing],
        strict_concept=False,
    )
    assert len(catalog) == 1
    assert catalog[0].concept == "StockholdersEquityOther"