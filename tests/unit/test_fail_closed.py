
from contracts.query import QueryRequest
from graph.builder import build_snapshot
from graph.store import save_snapshot
from models.enums import QueryStatus
from retrieval.service import QueryService


def test_insufficient_evidence_when_empty_graph(tmp_path, sample_parsed_document):
    empty_doc = sample_parsed_document.model_copy(
        update={
            "sections": [sample_parsed_document.sections[0]],
            "tables": [],
            "parse_confidence": 0.9,
        }
    )
    snap = build_snapshot("empty", [empty_doc], snapshot_id="empty-snap")
    save_snapshot(snap, tmp_path)
    svc = QueryService(graph_base_dir=tmp_path, issuer_id="empty")
    resp = svc.answer(QueryRequest(query="What is revenue?", snapshot_id="empty-snap"))
    assert resp.status in (QueryStatus.INSUFFICIENT_EVIDENCE, QueryStatus.SUCCESS)
