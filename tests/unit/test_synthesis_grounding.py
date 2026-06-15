"""Synthesis grounding fixes for MRR-ok VA=0 cohort."""

from __future__ import annotations

from datetime import date

from models.enums import EvidenceSourceType
from models.filing import FilingRef
from models.query import EvidenceChunk
from retrieval.synthesis import (
    _try_synthesize_business_segments,
    _try_synthesize_comparison_risk,
    _try_synthesize_divestiture,
    _try_synthesize_numeric_xbrl,
)


def _chunk(
    acc: str,
    excerpt: str,
    *,
    section_id: str = "html-md_and_a-1",
) -> EvidenceChunk:
    return EvidenceChunk(
        chunk_node_id=f"doc-{acc}-{section_id}-body",
        excerpt=excerpt,
        content_hash="abc",
        citation_label="MD&A",
        source_type=EvidenceSourceType.HTML,
        accession=acc,
        section_id=section_id,
    )


def _xbrl_chunk(excerpt: str) -> EvidenceChunk:
    return EvidenceChunk(
        chunk_node_id="doc-0000034088-26-000067-xbrl-1",
        excerpt=excerpt,
        content_hash="abc",
        citation_label="XBRL",
        source_type=EvidenceSourceType.XBRL,
        accession="0000034088-26-000067",
        section_id="xbrl-facts",
    )


def _filing(acc: str, *, form: str = "10-K", year: int = 2025) -> FilingRef:
    return FilingRef(
        cik="34088",
        accession=acc,
        form_type=form,
        filed_at=date(year, 12, 31),
        period_end=date(year, 12, 31),
        source_uri="https://example.com",
    )


def test_comparison_risk_skips_boilerplate_excerpts() -> None:
    cat = "0000018230-26-000021"
    xom = "0000034088-26-000067"
    evidence = [
        EvidenceChunk(
            chunk_node_id=f"doc-{cat}-html-risk_factors-1-body",
            excerpt=(
                "With respect to other income/expense, currency represents the effects of "
                "forward contracts entered into by the company."
            ),
            content_hash="a",
            citation_label="Risk Factors",
            source_type=EvidenceSourceType.HTML,
            accession=cat,
            section_id="html-risk_factors-1",
        ),
        EvidenceChunk(
            chunk_node_id=f"doc-{xom}-html-risk_factors-1-body",
            excerpt=(
                "Forward-looking statements regarding environmental sustainability efforts "
                "are not an indication that these statements are material to investors."
            ),
            content_hash="b",
            citation_label="Risk Factors",
            source_type=EvidenceSourceType.HTML,
            accession=xom,
            section_id="html-risk_factors-1",
        ),
    ]
    result = _try_synthesize_comparison_risk(
        evidence,
        "Compare geopolitical risks in Item 1A Risk Factors",
        [_filing(cat), _filing(xom)],
    )
    assert result is None


def test_divestiture_synthesis_extracts_amount_and_assets() -> None:
    acc = "0000034088-26-000067"
    evidence = [
        _chunk(
            acc,
            "During 2025 we completed divestitures totaling $1.1 billion, including the "
            "Singapore retail fuels business and Mobil Argentina S.A.",
        )
    ]
    result = _try_synthesize_divestiture(
        evidence,
        "Which business sales contributed to divestment proceeds?",
        [_filing(acc)],
    )
    assert result is not None
    text = result["answer"].text
    assert "1.1" in text
    assert "Singapore" in text
    assert "Mobil Argentina" in text


def test_business_segments_synthesis() -> None:
    acc = "0000034088-26-000067"
    evidence = [
        _chunk(
            acc,
            "ExxonMobil operates through Upstream, Energy Products, Chemical Products, "
            "and Specialty Products segments.",
            section_id="html-business_description-1",
        )
    ]
    result = _try_synthesize_business_segments(
        evidence,
        "What were ExxonMobil's primary business segments in its 2025 annual report?",
        [_filing(acc)],
    )
    assert result is not None
    text = result["answer"].text
    assert "Upstream" in text
    assert "Energy Products" in text


def test_numeric_xbrl_prefers_annual_2025_equity() -> None:
    evidence = [
        _xbrl_chunk(
            "XBRL StockholdersEquityOther: $664.00 million USD for period 2026-01-01 - 2026-04-01"
        ),
        _xbrl_chunk(
            "XBRL StockholdersEquity: $216.10 billion USD for period 2025-01-01 - 2025-12-31"
        ),
    ]
    result = _try_synthesize_numeric_xbrl(
        evidence,
        "What was Exxon Mobil's total shareholder equity at the end of the 2025 fiscal year?",
        [_filing("0000034088-26-000067")],
    )
    assert result is not None
    assert "StockholdersEquity" in result["answer"].text
    assert "216.10 billion" in result["answer"].text
