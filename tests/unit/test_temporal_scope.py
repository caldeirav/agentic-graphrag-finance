"""Unit tests for temporal scope intent (021/022)."""

from __future__ import annotations

from datetime import date, datetime

from models.filing import FilingRef
from models.graph import GraphManifest, GraphSnapshot
from retrieval.macro.pairing import annual_fiscal_year_requested, detect_quarterly_metric_cue
from retrieval.skills.temporal_scope import (
    infer_temporal_scope_intent,
    normalize_fiscal_period_labels,
    resolve_filings_to_intent,
    xbrl_period_matches_intent,
)


def test_annual_fiscal_year_disables_quarterly_cue() -> None:
    q = "What was revenue for fiscal year 2025?"
    assert annual_fiscal_year_requested(q) is True
    assert detect_quarterly_metric_cue(q) is False


def test_normalize_benchmark_period_formats() -> None:
    labels, target = normalize_fiscal_period_labels(["2025", "2025-FY"])
    assert labels == ["FY2025", "FY2025"]
    assert target == 2025


def test_infer_temporal_scope_prefers_fy10k() -> None:
    intent = infer_temporal_scope_intent(
        "What was Exxon Mobil total equity for fiscal year 2025?",
        fiscal_period_labels=["FY2025"],
    )
    assert intent.form_preference == "10-K"
    assert intent.target_fiscal_year == 2025
    assert "FY2025" in intent.period_labels


def test_quarter_query_prefers_10q() -> None:
    intent = infer_temporal_scope_intent("What was revenue in Q1 2025?")
    assert intent.form_preference == "10-Q"


def test_yoy_sets_comparison_mode() -> None:
    intent = infer_temporal_scope_intent(
        "How did net sales change year over year for fiscal year 2025?"
    )
    assert intent.comparison_mode == "yoy"


def test_xbrl_period_rejects_q1_next_year() -> None:
    intent = infer_temporal_scope_intent(
        "What was equity for fiscal year 2025?",
        fiscal_period_labels=["FY2025"],
    )
    assert xbrl_period_matches_intent(
        period_start="2026-01-01",
        period_end="2026-04-01",
        is_annual=False,
        intent=intent,
    ) is False


def test_xbrl_period_rejects_jan_end_prior_year_start_for_fy2025() -> None:
    intent = infer_temporal_scope_intent(
        "What was net profit margin for fiscal year 2025?",
        fiscal_period_labels=["FY2025"],
    )
    assert xbrl_period_matches_intent(
        period_start="2024-01-01",
        period_end="2025-01-01",
        is_annual=False,
        intent=intent,
    ) is False
    assert xbrl_period_matches_intent(
        period_start="2025-01-01",
        period_end="2025-12-31",
        is_annual=True,
        intent=intent,
    ) is True


def test_calendar_year_rebind_from_manifest() -> None:
    """March-FYE issuer: FY2025 label absent; calendar 2025 10-K should win."""
    fy26 = FilingRef(
        cik="34088",
        accession="0000034088-26-000067",
        form_type="10-K",
        filed_at=date(2026, 5, 4),
        period_end=date(2026, 3, 31),
        source_uri="",
    )
    cal2025 = FilingRef(
        cik="34088",
        accession="0000034088-26-000045",
        form_type="10-K",
        filed_at=date(2026, 2, 18),
        period_end=date(2025, 12, 31),
        source_uri="",
    )
    manifest = GraphManifest(
        created_at=datetime(2025, 1, 1),
        filing_refs=[fy26, cal2025],
        parser_version="test",
        graph_builder_version="test",
        storage_path="/tmp",
    )
    snap = GraphSnapshot(
        snapshot_id="snap",
        issuer_id="XOM",
        nodes=[],
        edges=[],
        manifest=manifest,
    )
    query = "What was total equity for fiscal year 2025?"
    intent = infer_temporal_scope_intent(query, fiscal_period_labels=["2025"])
    resolved, narrowed = resolve_filings_to_intent([fy26], snap, intent)
    assert resolved[0].accession == cal2025.accession
    assert fy26.accession in narrowed
