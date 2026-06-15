"""Comparison risk synthesis and excerpt ranking."""

from __future__ import annotations

from datetime import date

from models.enums import EvidenceSourceType, QueryStatus, Sufficiency
from models.filing import FilingRef
from models.query import AnswerPackage, EvidenceChunk
from retrieval.synthesis import (
    _extract_risk_sentences,
    _is_risk_comparison_query,
    _risk_topic_phrase,
    _try_synthesize_comparison_risk,
)


def _chunk(acc: str, excerpt: str) -> EvidenceChunk:
    return EvidenceChunk(
        chunk_node_id=f"doc-{acc}-html-risk_factors-1-body",
        excerpt=excerpt,
        content_hash="abc",
        citation_label="Item 1A. Risk Factors",
        source_type=EvidenceSourceType.HTML,
        accession=acc,
        section_id="html-risk_factors-1",
    )


def _filing(acc: str) -> FilingRef:
    return FilingRef(
        cik="0000000000",
        accession=acc,
        form_type="10-K",
        filed_at=date(2026, 3, 31),
        period_end=date(2026, 3, 31),
        source_uri="https://example.com",
    )


def test_risk_comparison_query_detection() -> None:
    q = "Compare geopolitical risks for Caterpillar and Exxon in their 10-K Risk Factors"
    assert _is_risk_comparison_query(q)


def test_comparison_risk_synthesis_structure() -> None:
    cat = "0000018230-26-000021"
    xom = "0000034088-26-000067"
    evidence = [
        _chunk(
            cat,
            "Our international operations expose us to geopolitical instability, trade tariffs, "
            "and sanctions that may adversely affect results.",
        ),
        _chunk(
            xom,
            "War, civil unrest, and international trade policies including tariffs and sanctions "
            "may disrupt our global operations.",
        ),
    ]
    query = (
        "Compare disclosures regarding geopolitical instability and international operations "
        "in Item 1A Risk Factors"
    )
    result = _try_synthesize_comparison_risk(
        evidence,
        query,
        [_filing(cat), _filing(xom)],
    )
    assert result is not None
    text = result["answer"].text
    assert "Item 1A. Risk Factors" in text
    assert cat in text
    assert xom in text
    assert "geopolitic" in text.lower() or "international" in text.lower()


def test_extract_risk_sentences_prefers_topic() -> None:
    excerpt = (
        "Total sales rose 22 percent in the first quarter. "
        "International operations face geopolitical instability and trade tariff risks."
    )
    sents = _extract_risk_sentences(excerpt, "geopolitical international trade risks")
    assert sents
    assert "geopolitical" in sents[0].lower()
