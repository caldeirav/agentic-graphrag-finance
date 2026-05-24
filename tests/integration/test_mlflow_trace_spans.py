import mlflow
import pytest

from contracts.query import QueryRequest
from graph.store import save_snapshot
from retrieval.service import QueryService


def test_mock_ask_has_mlflow_run_and_artifacts(tmp_path, sample_graph_snapshot, monkeypatch):
    monkeypatch.setenv("USE_MOCK_LLM", "1")
    monkeypatch.setenv("USE_MOCK_JUDGE", "1")
    save_snapshot(sample_graph_snapshot, tmp_path)
    svc = QueryService(graph_base_dir=tmp_path, issuer_id=sample_graph_snapshot.issuer_id)
    resp = svc.answer(
        QueryRequest(
            query="What was revenue?",
            snapshot_id=sample_graph_snapshot.snapshot_id,
            metadata={"issuer_id": sample_graph_snapshot.issuer_id, "trace_level": "quiet"},
        )
    )
    assert resp.mlflow_run_id
    client = mlflow.tracking.MlflowClient()
    run = client.get_run(resp.mlflow_run_id)
    assert run.info.run_id
    artifacts = {f.path for f in client.list_artifacts(resp.mlflow_run_id)}
    assert "agent_trajectory.json" in artifacts
