"""Unit tests for meso section scoring (009)."""

from __future__ import annotations

from retrieval.orchestration.meso_scoring import is_mda_query, score_section


def test_mda_query_boosts_md_and_a_over_xbrl_and_risk_item():
    q = "principal risk factors discussed in management discussion and analysis"
    assert is_mda_query(q)
    mda_score, _ = score_section(
        label="Management's Discussion and Analysis",
        node_id="doc-0000320193-25-000079-html-md_and_a-0",
        section_id="html-md_and_a-0",
        query=q,
        prefer_html=True,
        filing_accessions=["0000320193-25-000079"],
    )
    xbrl_score, _ = score_section(
        label="XBRL Financial Facts",
        node_id="doc-0000320193-25-000079-xbrl-facts",
        section_id="xbrl-facts",
        query=q,
        prefer_html=True,
        filing_accessions=["0000320193-25-000079"],
    )
    risk_score, _ = score_section(
        label="Item 1A. Risk Factors",
        node_id="doc-0000320193-25-000079-html-risk_factors-1",
        section_id="html-risk_factors-1",
        query=q,
        prefer_html=True,
        filing_accessions=["0000320193-25-000079"],
    )
    assert mda_score > xbrl_score
    assert mda_score > risk_score
