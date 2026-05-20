"""Evidence scoping to bound filings and anchor periods."""

from datetime import date

from models.filing import FilingRef
from models.query import EvidenceChunk
from retrieval.evidence_scope import (
    filter_evidence_for_filing_set,
    node_in_allowed_documents,
    parse_period_end_from_excerpt,
    period_alignment_score,
    period_matches_anchor,
)


def test_parse_period_end_iso_range():
    excerpt = (
        "XBRL RevenueFromContractWithCustomerExcludingAssessedTax: $124.30 billion USD "
        "for period 2024-09-29 - 2024-12-29"
    )
    assert parse_period_end_from_excerpt(excerpt) == date(2024, 12, 29)


def test_parse_period_end_us_range():
    excerpt = (
        "XBRL RevenueFromContractWithCustomerExcludingAssessedTax: $124.30 billion USD "
        "for period Sep 29, 2024 to Dec 29, 2024"
    )
    assert parse_period_end_from_excerpt(excerpt) == date(2024, 12, 29)


def test_period_matches_anchor_within_tolerance():
    anchor = date(2025, 12, 27)
    assert period_matches_anchor(date(2025, 12, 29), [anchor])
    assert not period_matches_anchor(date(2024, 12, 29), [anchor])


def test_period_matches_anchor_duration_range():
    anchor = date(2025, 12, 27)
    excerpt = "XBRL Revenue: $124.30 billion for period 2025-09-28 - 2025-12-28"
    assert period_matches_anchor(None, [anchor], excerpt=excerpt)


def test_period_alignment_penalizes_stale_quarter():
    anchors = [date(2025, 12, 27)]
    old = (
        "XBRL RevenueFromContract: $124.30 billion for period Sep 29, 2024 to Dec 29, 2024"
    )
    new = (
        "XBRL RevenueFromContract: $120.00 billion for period Sep 28, 2025 to Dec 27, 2025"
    )
    assert period_alignment_score(old, anchors) < 0
    assert period_alignment_score(new, anchors) > 0


def test_node_in_allowed_documents():
    doc = "doc-0000320193-26-000006"
    assert node_in_allowed_documents(f"{doc}-xbrl-abc", {doc})
    assert not node_in_allowed_documents("doc-0000320193-25-000057-xbrl-abc", {doc})


def test_filter_evidence_prefers_aligned_period():
    bound = FilingRef(
        cik="0000320193",
        accession="0000320193-26-000006",
        form_type="10-Q",
        filed_at=date(2026, 1, 30),
        period_end=date(2025, 12, 27),
        source_uri="u",
    )
    aligned = EvidenceChunk(
        chunk_node_id="doc-0000320193-26-000006-xbrl-a",
        excerpt="XBRL Revenue: $124.30 billion for period 2025-09-28 - 2025-12-28",
        content_hash="a",
        citation_label="Revenue",
    )
    stale = EvidenceChunk(
        chunk_node_id="doc-0000320193-26-000006-xbrl-b",
        excerpt="XBRL Revenue: $124.30 billion for period 2024-09-29 - 2024-12-29",
        content_hash="b",
        citation_label="Revenue",
    )
    other_doc = EvidenceChunk(
        chunk_node_id="doc-0000320193-25-000057-xbrl-c",
        excerpt="XBRL Revenue: $124.30 billion for period 2024-09-29 - 2024-12-29",
        content_hash="c",
        citation_label="Revenue",
    )
    filtered = filter_evidence_for_filing_set([stale, other_doc, aligned], [bound])
    assert filtered == [aligned]
