"""Unit tests for HTML table fallback (022-D)."""

from __future__ import annotations

from models.enums import EvidenceSourceType
from models.query import EvidenceChunk
from retrieval.skills.html_table_fallback import extract_from_html_tables
from retrieval.skills.temporal_scope import infer_temporal_scope_intent


def _html_chunk(text: str) -> EvidenceChunk:
    return EvidenceChunk(
        chunk_node_id="html-1",
        excerpt=text,
        content_hash="h",
        citation_label="HTML",
        source_type=EvidenceSourceType.HTML,
        section_id="HTML",
    )


def test_equity_rollforward_parses_fy2025_column() -> None:
    excerpt = """
    Stockholders' equity rollforward
                              2025              2024
    Total equity              $216.10 billion   $204.00 billion
    """
    temporal = infer_temporal_scope_intent(
        "What was total shareholder equity for fiscal year 2025?",
        fiscal_period_labels=["FY2025"],
    )
    hit = extract_from_html_tables(
        [_html_chunk(excerpt)],
        "What was total shareholder equity for fiscal year 2025?",
        temporal_intent=temporal,
    )
    assert hit is not None
    assert "216" in hit.value_display


def test_ambiguous_table_abstains() -> None:
    excerpt = "Miscellaneous financial data without row labels."
    hit = extract_from_html_tables(
        [_html_chunk(excerpt)],
        "What was total shareholder equity for fiscal year 2025?",
    )
    assert hit is None
