"""Tests for path-repair v2 heuristics."""

from __future__ import annotations

from evaluation.generation.path_sanitize import (
    is_divestiture_item,
    needs_v2_path_repair,
    pick_section_path_for_accession,
    quarter_year_from_question,
)


def test_quarter_year_from_question() -> None:
    assert quarter_year_from_question("According to Exxon Mobil's Q1 2026 report") == (1, 2026)
    assert quarter_year_from_question("first quarter of 2026") == (1, 2026)


def test_divestiture_detected() -> None:
    assert is_divestiture_item(
        "Which businesses were sold in the $1.1 billion divestment?",
        answer="Singapore retail fuels business",
    )


def test_needs_v2_when_divestiture_mapped_to_business() -> None:
    row = {
        "question": "According to Exxon Mobil's Q1 2026 report, which businesses were sold?",
        "ground_truth": {"answer": "Singapore retail fuels business and Mobil Argentina S.A."},
        "expected_section_paths": ["0000034088-26-000067/ITEM 1. BUSINESS"],
        "inspiration_profile": "financebench",
    }
    assert needs_v2_path_repair(row)


def test_pick_divestiture_path_prefers_10q_mda() -> None:
    graph_paths = {
        "0000034088-26-000067/ITEM 1. BUSINESS",
        "0000034088-26-000067/10-Q Exxon Mobil Corporation 2026-03-31",
        "0000034088-26-000067/Item 2. Management's Discussion and Analysis of Financial Condition and Results of Operations",
        "0000034088-26-000067/XBRL Financial Facts",
    }
    picked = pick_section_path_for_accession(
        "0000034088-26-000067",
        graph_paths,
        ["10-q", "management", "discussion"],
        question="According to Exxon Mobil's Q1 2026 report, which businesses were sold in divestment activities?",
        answer="Singapore retail fuels business",
    )
    assert picked is not None
    assert "business" not in picked.lower() or "10-q" in picked.lower() or "management" in picked.lower()
    assert "xbrl" not in picked.lower()
