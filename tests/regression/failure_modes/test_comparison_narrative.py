"""Regression: comparison narrative contrast (019 M4)."""

from __future__ import annotations

from datetime import date

from evaluation.generation.comparison_gt import _CROSS_VERB
from models.enums import EvidenceSourceType, QueryStatus
from models.filing import FilingRef
from models.query import EvidenceChunk
from retrieval.synthesis import _try_synthesize_comparison_narrative


def _filing(accession: str, *, form: str = "10-K") -> FilingRef:
    return FilingRef(
        cik="320193",
        accession=accession,
        form_type=form,
        filed_at=date(2024, 11, 1),
        period_end=date(2024, 9, 28),
        source_uri="",
    )


def test_cross_verb_pattern_matches_contrast_language() -> None:
    assert _CROSS_VERB.search("Company A increased while Company B decreased")
    assert not _CROSS_VERB.search("Company A reported revenue of $1B")


def test_comparison_narrative_includes_contrast_verbs() -> None:
    filing_a = _filing("0000320193-24-000123")
    filing_b = _filing("0000320193-24-000076")
    evidence = [
        EvidenceChunk(
            chunk_node_id="doc-0000320193-24-000123-html-c1",
            excerpt="Apple emphasizes services growth and margin expansion in North America.",
            content_hash="a",
            accession=filing_a.accession,
            section_id="Item7",
            source_type=EvidenceSourceType.HTML,
        ),
        EvidenceChunk(
            chunk_node_id="doc-0000320193-24-000076-html-c1",
            excerpt="Apple discusses supply chain resilience differently with greater Asia exposure.",
            content_hash="b",
            accession=filing_b.accession,
            section_id="Item7",
            source_type=EvidenceSourceType.HTML,
        ),
    ]
    result = _try_synthesize_comparison_narrative(
        evidence,
        "Compare how both filings discuss business performance.",
        [filing_a, filing_b],
    )
    assert result is not None
    text = result["answer"].text
    assert _CROSS_VERB.search(text)
    assert "Both" in text
    assert result["status"] == QueryStatus.SUCCESS
