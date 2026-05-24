"""Integration: NL macro binding via LangGraph (008 US1)."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

from graph.legacy_builder import build_snapshot
from models.filing import FilingRef
from models.parsing import ParsedDocument
from retrieval.orchestration.graph import build_agent_graph
from retrieval.orchestration.nodes.macro_router import macro_router


def _mock_api(snapshot):
    api = MagicMock()
    api.get_snapshot.return_value = snapshot
    return api


def _mini_snapshot() -> object:
    refs = [
        FilingRef(
            cik="0000320193",
            accession="0000320193-26-000013",
            form_type="10-Q",
            filed_at=date(2026, 5, 1),
            period_end=date(2026, 3, 28),
            source_uri="u1",
        ),
        FilingRef(
            cik="0000320193",
            accession="0000320193-26-000006",
            form_type="10-Q",
            filed_at=date(2026, 1, 30),
            period_end=date(2025, 12, 27),
            source_uri="u2",
        ),
        FilingRef(
            cik="0000320193",
            accession="0000320193-25-000079",
            form_type="10-K",
            filed_at=date(2025, 10, 31),
            period_end=date(2025, 9, 27),
            source_uri="u3",
        ),
    ]
    docs = [
        ParsedDocument(
            filing=r,
            sections=[],
            tables=[],
            footnotes=[],
            parse_confidence=1.0,
            parser_version="test",
            content_hash=r.accession,
        )
        for r in refs
    ]
    return build_snapshot("AAPL", docs, snapshot_id="nl-bind-test")


def test_macro_router_prior_quarter(monkeypatch):
    monkeypatch.setenv("USE_MOCK_LLM", "1")
    snap = _mini_snapshot()
    api = _mock_api(snap)
    state = {
        "query": "What was revenue in the prior quarter?",
        "snapshot_id": snap.snapshot_id,
        "filing_set": [],
        "cli_prebound": False,
    }
    out = macro_router(state, graph_api=api)
    assert not out.get("macro_binding_failed")
    assert len(out["filing_set"]) == 1
    assert out["filing_set"][0].accession == "0000320193-26-000006"
    assert out["macro_binding_record"].validation.status.value == "approved"


def test_macro_router_latest_annual_risk(monkeypatch):
    monkeypatch.setenv("USE_MOCK_LLM", "1")
    snap = _mini_snapshot()
    api = _mock_api(snap)
    state = {
        "query": "Summarize principal risk factors in the latest annual report",
        "snapshot_id": snap.snapshot_id,
        "filing_set": [],
        "cli_prebound": False,
    }
    out = macro_router(state, graph_api=api)
    assert len(out["filing_set"]) == 1
    assert out["filing_set"][0].form_type == "10-K"


def test_graph_compiles_with_macro_conditional():
    api = MagicMock()
    g = build_agent_graph(api)
    assert g is not None
