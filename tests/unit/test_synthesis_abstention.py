"""Synthesis abstention correction and YoY intent guards."""

from __future__ import annotations

from datetime import date

from models.enums import ComparisonMode, EvidenceSourceType, QueryIntent
from models.filing import FilingRef
from models.query import EvidenceChunk
from retrieval.synthesis import _correct_abstention_denial, _yoy_comparison_intent


def _chunk(acc: str, excerpt: str) -> EvidenceChunk:
    return EvidenceChunk(
        chunk_node_id=f"doc-{acc}-html-mda-1-body",
        excerpt=excerpt,
        content_hash="abc123",
        citation_label="MD&A",
        source_type=EvidenceSourceType.HTML,
        accession=acc,
        section_id="html-mda-1",
    )


def _filing(acc: str) -> FilingRef:
    return FilingRef(
        cik="34088",
        accession=acc,
        form_type="10-K",
        filed_at=date(2026, 3, 31),
        period_end=date(2026, 3, 31),
        source_uri="https://example.com",
    )


def test_yoy_intent_not_inferred_from_macro_on_single_filing() -> None:
    filing = _filing("0000034088-26-000067")
    state = {
        "filing_set": [filing],
        "macro_plan": type(
            "Plan",
            (),
            {"temporal_scope": type("TS", (), {"comparison_mode": ComparisonMode.YOY})()},
        )(),
    }
    assert _yoy_comparison_intent("What divestitures were completed?", state) is False


def test_abstention_correction_uses_mda_excerpt() -> None:
    filing = _filing("0000034088-26-000067")
    evidence = [
        _chunk(
            filing.accession,
            "During 2025 we completed divestitures of non-core assets totaling $1.1 billion.",
        )
    ]
    text = _correct_abstention_denial(
        "Based on the evidence, I cannot identify divestiture details.",
        query="What divestitures did Exxon complete?",
        evidence=evidence,
        filing_set=[filing],
    )
    assert "cannot identify" not in text.lower()
    assert "1.1 billion" in text
