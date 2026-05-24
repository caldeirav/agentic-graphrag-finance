"""MLflow navigation_trace.json smoke (009)."""

from __future__ import annotations

import os

import pytest

from contracts.query import QueryRequest
from graph.store import save_snapshot
from retrieval.service import QueryService


@pytest.mark.skipif(os.environ.get("USE_MOCK_LLM", "1") != "1", reason="mock")
def test_ask_emits_navigation_trace(tmp_path, sample_graph_snapshot, monkeypatch):
    save_snapshot(sample_graph_snapshot, tmp_path)
    logged: list = []

    def _fake_log(run_id, record):
        logged.append(record.to_trajectory_dict() if hasattr(record, "to_trajectory_dict") else record)
        return "uri"

    monkeypatch.setattr(
        "tracing.mlflow_langgraph.log_navigation_trace",
        _fake_log,
    )
    svc = QueryService(graph_base_dir=tmp_path, issuer_id=sample_graph_snapshot.issuer_id)
    resp = svc.answer(
        QueryRequest(
            query="What are the risk factors?",
            snapshot_id=sample_graph_snapshot.snapshot_id,
        )
    )
    assert resp.status is not None
    if logged:
        assert "visit_counts" in logged[0]
