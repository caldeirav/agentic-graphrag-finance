"""Unit tests for TOC planner heuristics."""

from __future__ import annotations

from retrieval.navigation.toc_planner import (
    TocEntry,
    TocPlanResult,
    apply_toc_heuristics,
    is_financial_numeric_query,
)


def test_yoy_net_sales_is_financial_numeric():
    q = "How did total net sales change year over year?"
    assert is_financial_numeric_query(q)


def test_apply_toc_heuristics_prefers_xbrl_for_yoy_revenue():
    toc = [
        TocEntry(
            section_node_id="doc-x-html-business_description-0",
            section_id="html-business_description-0",
            label="Item 1.",
            narrative_kind="business_description",
        ),
        TocEntry(
            section_node_id="doc-x-xbrl-facts",
            section_id="xbrl-facts",
            label="XBRL Financial Facts",
            narrative_kind="xbrl_bucket",
        ),
    ]
    plan = TocPlanResult(
        accession="0000320193-25-000079",
        ranked_section_node_ids=["doc-x-html-business_description-0"],
        primary_narrative_kind="business_description",
    )
    out = apply_toc_heuristics(
        "How did total net sales change year over year?",
        plan,
        toc,
    )
    assert out.primary_narrative_kind == "xbrl_bucket"
    assert out.ranked_section_node_ids == ["doc-x-xbrl-facts"]
