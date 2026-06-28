"""Unit tests for macro planner temporal hints (020)."""

from __future__ import annotations

import json
from datetime import date, datetime
from unittest.mock import MagicMock, patch

from models.graph import GraphManifest, GraphSnapshot
from models.filing import FilingRef
from retrieval.macro.planner import plan_macro_binding


def _snapshot() -> GraphSnapshot:
    ref = FilingRef(
        cik="320193",
        accession="0000320193-25-000123",
        form_type="10-K",
        filed_at=date(2025, 11, 1),
        period_end=date(2025, 9, 28),
        source_uri="",
    )
    manifest = GraphManifest(
        created_at=datetime(2025, 1, 1),
        filing_refs=[ref],
        parser_version="test",
        graph_builder_version="test",
        storage_path="/tmp",
    )
    return GraphSnapshot(
        snapshot_id="snap-1",
        issuer_id="AAPL",
        nodes=[],
        edges=[],
        manifest=manifest,
    )


def test_plan_macro_binding_includes_fiscal_hints_in_prompt() -> None:
    snap = _snapshot()
    mock_resp = MagicMock()
    mock_resp.content = json.dumps(
        {
            "intent_summary": "FY2025 revenue",
            "comparison_mode": "none",
            "anchor": "latest_annual",
            "proposed_accessions": ["0000320193-25-000123"],
            "is_comparison": False,
            "quarterly_metric_cue": False,
        }
    )
    captured_prompt = ""

    def fake_invoke(stage, llm, messages):
        nonlocal captured_prompt
        captured_prompt = messages[1].content
        return mock_resp, {}

    with patch("retrieval.macro.planner.traced_llm_invoke", side_effect=fake_invoke):
        with patch.dict("os.environ", {"USE_MOCK_LLM": "0"}):
            plan_macro_binding(
                "What was revenue for fiscal year 2025?",
                snap,
                temporal_anchor="FY2025",
                fiscal_period_labels=["FY2025"],
            )
    assert "FY2025" in captured_prompt
    assert "Benchmark fiscal periods" in captured_prompt
