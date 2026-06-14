"""Tests for selective benchmark path injection."""

from __future__ import annotations

from retrieval.navigation.benchmark_injection import (
    filter_benchmark_injection_paths,
    is_safe_benchmark_injection_path,
)


def test_suppress_blocks_item_1_business_path() -> None:
    path = "0000034088-26-000067/ITEM 1. BUSINESS"
    assert not is_safe_benchmark_injection_path(path)
    out = filter_benchmark_injection_paths(
        [path],
        suppress_benchmark_path_injection=True,
    )
    assert out == []


def test_suppress_allows_mda_and_10q_paths() -> None:
    paths = [
        "0000034088-26-000067/10-Q Exxon Mobil Corporation 2026-03-31",
        "0000034088-26-000067/Item 2. Management's Discussion and Analysis of Financial Condition and Results of Operations",
    ]
    for path in paths:
        assert is_safe_benchmark_injection_path(path)
    out = filter_benchmark_injection_paths(
        paths,
        suppress_benchmark_path_injection=True,
    )
    assert out == paths


def test_no_suppress_keeps_all_valid_paths() -> None:
    paths = [
        "0000034088-26-000067/ITEM 1. BUSINESS",
        "0000034088-26-000067/10-Q Exxon Mobil Corporation 2026-03-31",
    ]
    out = filter_benchmark_injection_paths(
        paths,
        suppress_benchmark_path_injection=False,
    )
    assert out == paths


def test_apply_toc_heuristics_divestiture_prefers_mda() -> None:
    from retrieval.navigation.toc_planner import (
        TocEntry,
        TocPlanResult,
        apply_toc_heuristics,
    )

    toc = [
        TocEntry(
            section_node_id="doc-x-html-business_description-0",
            section_id="html-business_description-0",
            label="Item 1. Business",
            narrative_kind="business_description",
        ),
        TocEntry(
            section_node_id="doc-x-html-md_and_a-4",
            section_id="html-md_and_a-4",
            label="Item 2. MD&A",
            narrative_kind="md_and_a",
        ),
    ]
    plan = TocPlanResult(
        accession="0000034088-26-000067",
        ranked_section_node_ids=["doc-x-html-business_description-0"],
        primary_narrative_kind="business_description",
    )
    out = apply_toc_heuristics(
        "Which businesses were sold in divestment activities totaling $1.1 billion?",
        plan,
        toc,
    )
    assert out.primary_narrative_kind == "md_and_a"
    assert out.ranked_section_node_ids == ["doc-x-html-md_and_a-4"]
    assert "business_description" in out.exclude_kinds
