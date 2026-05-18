from contracts.query import QueryRequest
from graph.store import save_snapshot
from models.enums import QueryStatus
from retrieval.service import QueryService


def test_full_query_flow_mock_llm(tmp_path, sample_graph_snapshot):
    save_snapshot(sample_graph_snapshot, tmp_path)
    svc = QueryService(graph_base_dir=tmp_path, issuer_id="0000320193")
    resp = svc.answer(
        QueryRequest(
            query="What are total assets in 2024?",
            snapshot_id=sample_graph_snapshot.snapshot_id,
        )
    )
    assert resp.status == QueryStatus.SUCCESS
    assert resp.answer is not None
    assert len(resp.answer.citations) >= 0
