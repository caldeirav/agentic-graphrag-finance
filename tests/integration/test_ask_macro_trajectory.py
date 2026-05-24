"""MLflow macro_binding.json smoke test (T029)."""

from __future__ import annotations

from pathlib import Path

import mlflow

from contracts.query import QueryRequest
from graph.store import save_snapshot
from retrieval.service import QueryService
from tracing.mlflow_langgraph import setup_mlflow


def test_macro_binding_artifact_logged(tmp_path, aapl_macro_snapshot, monkeypatch):
    monkeypatch.setenv("USE_MOCK_LLM", "1")
    setup_mlflow()
    graphs = tmp_path / "graphs"
    save_snapshot(aapl_macro_snapshot, graphs)
    svc = QueryService(graph_base_dir=graphs, issuer_id="AAPL")
    resp = svc.answer(
        QueryRequest(
            query="What was revenue in the prior quarter?",
            snapshot_id=aapl_macro_snapshot.snapshot_id,
            metadata={"binding_deferred": "true"},
        )
    )
    assert resp.mlflow_run_id
    client = mlflow.tracking.MlflowClient()
    artifacts = [a.path for a in client.list_artifacts(resp.mlflow_run_id)]
    assert any("macro_binding.json" in p for p in artifacts)
    import json
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        client.download_artifacts(resp.mlflow_run_id, "macro_binding.json", td)
        payload = json.loads(Path(td).joinpath("macro_binding.json").read_text())
    assert payload.get("validation_status") == "approved"
    assert payload.get("selected_accessions")
    assert payload.get("rationale")
