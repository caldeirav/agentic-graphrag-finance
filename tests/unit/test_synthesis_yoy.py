"""YoY net sales synthesis and LLM response normalization."""

from datetime import date

from models.enums import ComparisonMode, QueryStatus
from models.filing import FilingRef
from models.query import EvidenceChunk, MacroPlan, TemporalScope
from retrieval.synthesis import (
    _message_content_to_text,
    _response_text,
    _synthesize_yoy_net_sales,
    synthesize,
)


def test_message_content_to_text_strips_thinking():
    think_open, think_close = "<" + "think" + ">", "<" + "/" + "think" + ">"
    content = f"{think_open}reasoning here{think_close}Net sales rose 6%."
    assert _message_content_to_text(content) == "Net sales rose 6%."


def test_response_text_from_text_blocks():
    resp = type("R", (), {"content": [{"type": "text", "text": "Answer."}]})()
    assert _response_text(resp) == "Answer."


def test_synthesize_yoy_net_sales_two_10k():
    fy25 = FilingRef(
        cik="0000320193",
        accession="0000320193-25-000079",
        form_type="10-K",
        filed_at=date(2025, 11, 1),
        period_end=date(2025, 9, 27),
        source_uri="https://example.com",
    )
    fy24 = FilingRef(
        cik="0000320193",
        accession="0000320193-24-000123",
        form_type="10-K",
        filed_at=date(2024, 11, 1),
        period_end=date(2024, 9, 28),
        source_uri="https://example.com",
    )
    evidence = [
        EvidenceChunk(
            chunk_node_id="doc-0000320193-25-000079-xbrl-a",
            excerpt=(
                "XBRL RevenueFromContractWithCustomerExcludingAssessedTax: $416.16 billion USD "
                "for period 2024-09-29 - 2025-09-28"
            ),
            content_hash="a",
            citation_label="Revenue",
        ),
        EvidenceChunk(
            chunk_node_id="doc-0000320193-24-000123-xbrl-b",
            excerpt=(
                "XBRL RevenueFromContractWithCustomerExcludingAssessedTax: $391.04 billion USD "
                "for period 2023-10-01 - 2024-09-29"
            ),
            content_hash="b",
            citation_label="Revenue",
        ),
    ]
    text = _synthesize_yoy_net_sales(
        evidence,
        [fy25, fy24],
        "How did total net sales change year over year?",
        state={
            "macro_plan": MacroPlan(
                intent_summary="yoy",
                temporal_scope=TemporalScope(
                    anchor_periods=[fy25.period_end, fy24.period_end],
                    comparison_mode=ComparisonMode.YOY,
                ),
                rationale="",
            )
        },
    )
    assert text is not None
    assert "416.16" in text
    assert "391.04" in text
    assert "increased" in text.lower()


def test_synthesize_empty_llm_uses_yoy_deterministic(monkeypatch):
    monkeypatch.setenv("USE_MOCK_LLM", "0")

    class _EmptyLLM:
        def invoke(self, messages):
            return type("R", (), {"content": []})()

    monkeypatch.setattr("retrieval.synthesis.create_chat_llm", lambda **kw: _EmptyLLM())
    fy25 = FilingRef(
        cik="0000320193",
        accession="0000320193-25-000079",
        form_type="10-K",
        filed_at=date(2025, 11, 1),
        period_end=date(2025, 9, 27),
        source_uri="https://example.com",
    )
    fy24 = FilingRef(
        cik="0000320193",
        accession="0000320193-24-000123",
        form_type="10-K",
        filed_at=date(2024, 11, 1),
        period_end=date(2024, 9, 28),
        source_uri="https://example.com",
    )
    evidence = [
        EvidenceChunk(
            chunk_node_id="doc-0000320193-25-000079-xbrl-a",
            excerpt=(
                "XBRL RevenueFromContractWithCustomerExcludingAssessedTax: $416.16 billion USD "
                "for period 2024-09-29 - 2025-09-28"
            ),
            content_hash="a",
            citation_label="Revenue",
        ),
        EvidenceChunk(
            chunk_node_id="doc-0000320193-24-000123-xbrl-b",
            excerpt=(
                "XBRL RevenueFromContractWithCustomerExcludingAssessedTax: $391.04 billion USD "
                "for period 2023-10-01 - 2024-09-29"
            ),
            content_hash="b",
            citation_label="Revenue",
        ),
    ]
    out = synthesize(
        {
            "evidence_chunks": evidence,
            "query": "How did total net sales change year over year?",
            "filing_set": [fy25, fy24],
            "macro_plan": MacroPlan(
                intent_summary="yoy",
                temporal_scope=TemporalScope(
                    anchor_periods=[fy25.period_end, fy24.period_end],
                    comparison_mode=ComparisonMode.YOY,
                ),
                rationale="",
            ),
        }
    )
    assert out["status"] == QueryStatus.SUCCESS
    assert "Based on" not in out["answer"].text
    assert "416.16" in out["answer"].text
    assert out.get("synthesis_fallback") == "yoy_deterministic"


def test_synthesize_yoy_net_sales_intra_filing_single_10k():
    fy25 = FilingRef(
        cik="0000320193",
        accession="0000320193-26-000006",
        form_type="10-K",
        filed_at=date(2026, 1, 30),
        period_end=date(2025, 12, 28),
        source_uri="https://example.com",
    )
    evidence = [
        EvidenceChunk(
            chunk_node_id="doc-0000320193-26-000006-xbrl-a",
            excerpt=(
                "XBRL RevenueFromContractWithCustomerExcludingAssessedTax: $416.16 billion USD "
                "for period 2024-09-29 - 2025-09-28"
            ),
            content_hash="a",
            citation_label="Revenue",
        ),
        EvidenceChunk(
            chunk_node_id="doc-0000320193-26-000006-xbrl-b",
            excerpt=(
                "XBRL RevenueFromContractWithCustomerExcludingAssessedTax: $391.04 billion USD "
                "for period 2023-10-01 - 2024-09-29"
            ),
            content_hash="b",
            citation_label="Revenue",
        ),
    ]
    text = _synthesize_yoy_net_sales(
        evidence,
        [fy25],
        "How did total net sales change year over year?",
        state={
            "macro_plan": MacroPlan(
                intent_summary="yoy",
                temporal_scope=TemporalScope(
                    anchor_periods=[fy25.period_end],
                    comparison_mode=ComparisonMode.YOY,
                ),
                rationale="",
            )
        },
    )
    assert text is not None
    assert "416.16" in text
    assert "391.04" in text
    assert "increased" in text.lower()
