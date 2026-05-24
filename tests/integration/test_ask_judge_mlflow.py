import mlflow

from contracts.query import QueryRequest
from graph.store import save_snapshot
from retrieval.service import QueryService


def test_ask_logs_trajectory_validation_and_judge(tmp_path, sample_graph_snapshot, monkeypatch):
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
    artifacts = {f.path for f in client.list_artifacts(resp.mlflow_run_id)}
    assert "agent_trajectory.json" in artifacts
    eval_children = {f.path for f in client.list_artifacts(resp.mlflow_run_id, "evaluation")}
    assert "evaluation/trajectory_validation.json" in eval_children or any(
        "trajectory_validation" in p for p in artifacts
    )
    assert "evaluation/judge_verdict.json" in eval_children or any(
        "judge_verdict" in p for p in artifacts
    )
    run = client.get_run(resp.mlflow_run_id)
    judge_metrics = [k for k in run.data.metrics if k.startswith("judge.")]
    assert judge_metrics, f"expected judge.* metrics, got {run.data.metrics}"
    assert resp.judge_status in ("ok", "degraded", "not_evaluable")
