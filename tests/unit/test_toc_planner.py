"""Unit tests for meso TOC planner."""

from __future__ import annotations

import pytest

from evaluation.fixtures.navigation_eval_snapshot import build_navigation_eval_snapshot
from retrieval.navigation.toc_planner import build_filing_toc, plan_meso_sections_toc


@pytest.fixture
def nav_snap():
    return build_navigation_eval_snapshot()


def test_build_filing_toc_includes_narrative_kind(nav_snap):
    filing = nav_snap.manifest.filing_refs[0]
    toc = build_filing_toc(nav_snap, filing)
    kinds = {e.narrative_kind for e in toc}
    assert "md_and_a" in kinds
    assert "risk_factors" in kinds


def test_mock_toc_planner_prefers_mda_over_risk(nav_snap, monkeypatch):
    monkeypatch.setenv("USE_MOCK_LLM", "1")
    filing = nav_snap.manifest.filing_refs[0]
    toc = build_filing_toc(nav_snap, filing)
    plan = plan_meso_sections_toc(
        query="principal risk factors in management discussion and analysis",
        filing=filing,
        toc=toc,
    )
    assert plan.primary_narrative_kind == "md_and_a"
    assert "risk_factors" in plan.exclude_kinds
    assert plan.ranked_section_node_ids
    assert all("md_and_a" in sid or "mda" in sid for sid in plan.ranked_section_node_ids)
