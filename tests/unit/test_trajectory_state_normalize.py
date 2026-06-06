"""Tests for trajectory snapshot hydration in deferred judge batch."""

from tracing.mlflow_langgraph import build_trajectory_from_state


def test_build_trajectory_from_snapshot_hydrates_evidence() -> None:
    snapshot = {
        "schema_version": "1.0.0",
        "query_id": "q1",
        "query_text": "What are the risk factors?",
        "document_route": [
            {
                "accession": "0000034088-26-000045",
                "form_type": "10-K",
                "cik": "0000034088",
                "filed_at": "2026-02-18",
                "period_end": "2025-12-31",
            }
        ],
        "graph_traversal": [],
        "evidence": [
            {
                "chunk_node_id": "doc-0000034088-26-000045-html-risk_factors-1-body",
                "content_hash": "abc",
                "citation_label": "Risk Factors",
                "source_type": "html",
                "accession": "0000034088-26-000045",
                "section_id": "html-risk_factors-1",
            }
        ],
    }
    trajectory = build_trajectory_from_state(snapshot)
    assert len(trajectory.evidence) == 1
    assert trajectory.evidence[0].chunk_node_id.endswith("html-risk_factors-1-body")
