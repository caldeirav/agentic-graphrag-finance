from contracts.query import QueryRequest, QueryResponse
from graph.store import save_snapshot
from retrieval.service import QueryService


def test_query_service_returns_response(tmp_path, sample_graph_snapshot):
    save_snapshot(sample_graph_snapshot, tmp_path)
    svc = QueryService(graph_base_dir=tmp_path, issuer_id="0000320193")
    resp = svc.answer(
        QueryRequest(
            query="How did total assets change?",
            snapshot_id=sample_graph_snapshot.snapshot_id,
        )
    )
    assert isinstance(resp, QueryResponse)
    assert resp.mlflow_run_id
