"""Integration: macro fail-closed paths (US3 / FR-010)."""

from __future__ import annotations

from unittest.mock import MagicMock

from models.enums import QueryStatus
from retrieval.orchestration.graph import build_agent_graph
from retrieval.orchestration.nodes.macro_router import macro_router


def _sparse_snapshot(aapl_macro_snapshot):
    snap = aapl_macro_snapshot
    snap.manifest.filing_refs = [snap.manifest.filing_refs[0]]
    return snap


def test_comparison_on_sparse_corpus_fails(monkeypatch, aapl_macro_snapshot):
    monkeypatch.setenv("USE_MOCK_LLM", "1")
    snap = _sparse_snapshot(aapl_macro_snapshot)
    api = MagicMock()
    api.get_snapshot.return_value = snap
    out = macro_router(
        {
            "query": "How did revenue change year over year?",
            "snapshot_id": snap.snapshot_id,
            "filing_set": [],
            "cli_prebound": False,
        },
        graph_api=api,
    )
    assert out.get("macro_binding_failed")
    assert out.get("status") == QueryStatus.ERROR
    assert out.get("answer") is not None
    assert "Macro binding failed" in out["answer"].text


def test_graph_short_circuits_on_macro_failure(monkeypatch, aapl_macro_snapshot):
    monkeypatch.setenv("USE_MOCK_LLM", "1")
    snap = _sparse_snapshot(aapl_macro_snapshot)
    api = MagicMock()
    api.get_snapshot.return_value = snap
    g = build_agent_graph(api)
    result = g.invoke(
        {
            "query": "How did revenue change year over year?",
            "snapshot_id": snap.snapshot_id,
            "filing_set": [],
            "cli_prebound": False,
            "section_candidates": [],
            "evidence_chunks": [],
        }
    )
    assert result.get("macro_binding_failed")
    assert not result.get("evidence_chunks")


SCENARIOS = [
    "year over year and quarter over quarter revenue",
    "How did revenue change year over year?",
    "Quarter over quarter net sales",
    "Compare YoY and QoQ revenue",
]


def test_fail_closed_scenario_matrix(monkeypatch, aapl_macro_snapshot):
    """SC-004: multiple misalignment / sparse scenarios return failed binding."""
    monkeypatch.setenv("USE_MOCK_LLM", "1")
    snap = _sparse_snapshot(aapl_macro_snapshot)
    api = MagicMock()
    api.get_snapshot.return_value = snap
    failures = 0
    for q in SCENARIOS:
        out = macro_router(
            {
                "query": q,
                "snapshot_id": snap.snapshot_id,
                "filing_set": [],
                "cli_prebound": False,
            },
            graph_api=api,
        )
        if out.get("macro_binding_failed"):
            failures += 1
    assert failures >= 3
