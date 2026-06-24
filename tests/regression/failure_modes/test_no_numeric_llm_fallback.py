"""Regression: numeric XBRL queries must not fall through to narrative LLM (023 M1)."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from models.enums import EvidenceSourceType, QueryStatus
from models.filing import FilingRef
from models.query import EvidenceChunk
from retrieval.synthesis import synthesize


def _xbrl_chunk(excerpt: str = "XBRL NetIncomeLoss: $100 million USD for period 2024-09-28") -> EvidenceChunk:
    return EvidenceChunk(
        chunk_node_id="doc-0000320193-24-000123-xbrl-1",
        excerpt=excerpt,
        content_hash="h",
        source_type=EvidenceSourceType.XBRL,
        accession="0000320193-24-000123",
        section_id="XBRL",
    )


def _filing() -> FilingRef:
    return FilingRef(
        cik="0000320193",
        accession="0000320193-24-000123",
        form_type="10-K",
        filed_at=date(2024, 11, 1),
        period_end=date(2024, 9, 28),
        source_uri="",
    )


def test_numeric_xbrl_abstains_without_llm_fallback(monkeypatch) -> None:
    monkeypatch.delenv("USE_MOCK_LLM", raising=False)
    state = {
        "evidence_chunks": [_xbrl_chunk()],
        "query": "What was the net profit margin?",
        "filing_set": [_filing()],
    }

    with patch(
        "retrieval.synthesis._try_computed_numeric_synthesis",
        return_value={
            "answer": type(
                "A",
                (),
                {
                    "text": "Insufficient evidence.",
                    "citations": [],
                    "sufficiency": "insufficient",
                },
            )(),
            "status": QueryStatus.INSUFFICIENT_EVIDENCE,
        },
    ):
        with patch("retrieval.synthesis._synthesize_with_llm") as live_llm:
            with patch("retrieval.synthesis._try_structured_synthesis") as structured:
                out = synthesize(state)

    live_llm.assert_not_called()
    structured.assert_not_called()
    assert out["synthesis_path"] == "numeric_abstain"


def test_numeric_xbrl_blocks_fallback_when_computed_returns_none(monkeypatch) -> None:
    monkeypatch.delenv("USE_MOCK_LLM", raising=False)
    state = {
        "evidence_chunks": [_xbrl_chunk()],
        "query": "What was revenue?",
        "filing_set": [_filing()],
        "numeric_llm_fallback_blocked": True,
    }

    with patch("retrieval.synthesis._try_computed_numeric_synthesis", return_value=None):
        with patch("retrieval.synthesis._synthesize_with_llm") as live_llm:
            with patch("retrieval.synthesis._try_structured_synthesis") as structured:
                out = synthesize(state)

    live_llm.assert_not_called()
    structured.assert_not_called()
    assert out["synthesis_path"] == "numeric_abstain"
    assert out["status"] == QueryStatus.INSUFFICIENT_EVIDENCE


def test_non_xbrl_query_may_use_live_llm(monkeypatch) -> None:
    monkeypatch.delenv("USE_MOCK_LLM", raising=False)
    filing = _filing()
    evidence = [
        EvidenceChunk(
            chunk_node_id="doc-0000320193-24-000123-html-mda-1",
            excerpt="We completed divestitures totaling $1.1 billion.",
            content_hash="h",
            source_type=EvidenceSourceType.HTML,
            accession=filing.accession,
            section_id="mda",
        )
    ]
    state = {
        "evidence_chunks": evidence,
        "query": "What divestitures were completed?",
        "filing_set": [filing],
    }

    with patch("retrieval.synthesis._try_computed_numeric_synthesis", return_value=None):
        with patch(
            "retrieval.synthesis._try_structured_synthesis",
            return_value=None,
        ):
            with patch(
                "retrieval.synthesis._synthesize_with_llm",
                return_value={
                    "answer": type(
                        "A",
                        (),
                        {
                            "text": "Divestitures totaled $1.1 billion.",
                            "citations": evidence,
                            "sufficiency": "complete",
                        },
                    )(),
                    "status": QueryStatus.SUCCESS,
                },
            ):
                out = synthesize(state)

    assert out["synthesis_path"] == "live_llm"
