"""Synthesis temporal anchor guidance for prior-quarter queries."""

from datetime import date

from models.filing import FilingRef
from models.query import EvidenceChunk
from retrieval.evidence_scope import filter_evidence_for_filing_set
from retrieval.synthesis import _temporal_synthesis_guidance


def test_prior_quarter_guidance_clarifies_bound_filing():
    filing = FilingRef(
        cik="0000320193",
        accession="0000320193-26-000006",
        form_type="10-Q",
        filed_at=date(2026, 1, 30),
        period_end=date(2025, 12, 27),
        source_uri="u",
    )
    text = _temporal_synthesis_guidance(
        "prior-quarter",
        [filing],
        period_ends="2025-12-27",
    )
    assert "prior fiscal quarter" in text
    assert "do not refuse" in text
    assert "2025-12-27" in text


def test_filter_keeps_aligned_revenue_not_prior_year():
    filing = FilingRef(
        cik="0000320193",
        accession="0000320193-26-000006",
        form_type="10-Q",
        filed_at=date(2026, 1, 30),
        period_end=date(2025, 12, 27),
        source_uri="u",
    )
    current = EvidenceChunk(
        chunk_node_id="doc-0000320193-26-000006-xbrl-a",
        excerpt=(
            "XBRL RevenueFromContractWithCustomerExcludingAssessedTax: $143.76 billion USD "
            "for period 2025-09-28 - 2025-12-28"
        ),
        content_hash="a",
    )
    prior_year = EvidenceChunk(
        chunk_node_id="doc-0000320193-26-000006-xbrl-b",
        excerpt=(
            "XBRL RevenueFromContractWithCustomerExcludingAssessedTax: $124.30 billion USD "
            "for period 2024-09-29 - 2024-12-29"
        ),
        content_hash="b",
    )
    filtered = filter_evidence_for_filing_set([current, prior_year], [filing])
    assert len(filtered) == 1
    assert "143.76" in filtered[0].excerpt
