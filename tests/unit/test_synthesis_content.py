"""LLM response content normalization."""

from datetime import date

from models.enums import QueryStatus
from models.filing import FilingRef
from models.query import EvidenceChunk
from retrieval.synthesis import _message_content_to_text, synthesize


def test_message_content_to_text_list_blocks():
    content = [{"type": "text", "text": "Revenue was $100B."}]
    assert _message_content_to_text(content) == "Revenue was $100B."


def test_synthesize_falls_back_when_llm_returns_empty(monkeypatch):
    monkeypatch.setenv("USE_MOCK_LLM", "0")

    class _EmptyLLM:
        def invoke(self, messages):
            return type("R", (), {"content": []})()

    monkeypatch.setattr("retrieval.synthesis.create_chat_llm", lambda **kw: _EmptyLLM())
    evidence = [
        EvidenceChunk(
            chunk_node_id="doc-0000320193-26-000006-xbrl-c1",
            excerpt=(
                "XBRL RevenueFromContract: $95.00 billion USD "
                "for period 2025-09-28 - 2025-12-27"
            ),
            content_hash="abc",
            citation_label="xbrl:Revenue",
        )
    ]
    filing = FilingRef(
        cik="0000320193",
        accession="0000320193-26-000006",
        form_type="10-Q",
        filed_at=date(2026, 1, 30),
        period_end=date(2025, 12, 27),
        source_uri="https://example.com",
    )
    stale = EvidenceChunk(
        chunk_node_id="doc-0000320193-25-000057-xbrl-stale",
        excerpt="XBRL Revenue: $124.30 billion for period 2024-09-29 - 2024-12-29",
        content_hash="stale",
        citation_label="Revenue",
    )
    out = synthesize(
        {
            "evidence_chunks": [stale, *evidence],
            "query": "Revenue?",
            "filing_set": [filing],
        }
    )
    assert out["answer"].text
    assert out["status"] == QueryStatus.SUCCESS
