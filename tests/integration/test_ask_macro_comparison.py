"""Integration: YoY and QoQ macro binding (US2)."""

from __future__ import annotations

from unittest.mock import MagicMock

from retrieval.orchestration.nodes.macro_router import macro_router


def _run(query: str, snap):
    api = MagicMock()
    api.get_snapshot.return_value = snap
    return macro_router(
        {
            "query": query,
            "snapshot_id": snap.snapshot_id,
            "filing_set": [],
            "cli_prebound": False,
        },
        graph_api=api,
    )


def test_yoy_revenue_binds_two_accessions(monkeypatch, aapl_macro_snapshot):
    monkeypatch.setenv("USE_MOCK_LLM", "1")
    out = _run("How did revenue change year over year?", aapl_macro_snapshot)
    assert not out.get("macro_binding_failed")
    accs = {f.accession for f in out["filing_set"]}
    assert len(accs) == 2
    assert "0000320193-26-000013" in accs
    assert accs & {"0000320193-25-000057", "0000320193-25-000073"}


def test_qoq_binds_sequential_quarters(monkeypatch, aapl_macro_snapshot):
    monkeypatch.setenv("USE_MOCK_LLM", "1")
    out = _run("How did revenue change quarter over quarter?", aapl_macro_snapshot)
    assert len(out["filing_set"]) == 2
    accs = [f.accession for f in out["filing_set"]]
    assert accs == ["0000320193-26-000013", "0000320193-26-000006"]
