"""Unit: normalize serialized filing_set dicts for judge-batch trajectories."""

from __future__ import annotations

from tracing.mlflow_langgraph import build_trajectory_from_state
from tracing.trajectory_export import build_agent_trajectory_snapshot, normalize_trajectory_state


def test_normalize_coerces_filing_set_dicts() -> None:
    state = normalize_trajectory_state(
        {
            "query": "Compare filings",
            "filing_set": [
                {
                    "cik": "0000080424",
                    "accession": "0000080424-25-000012",
                    "form_type": "10-K",
                    "filed_at": "2025-08-01",
                    "period_end": "2025-06-30",
                    "source_uri": "",
                }
            ],
            "evidence_chunks": [
                {
                    "chunk_node_id": "doc-0000080424-25-000012-html-business-1-body",
                    "content_hash": "abc",
                    "source_type": "html",
                    "section_id": "html-business-1",
                }
            ],
        }
    )
    snapshot = build_agent_trajectory_snapshot(state)
    assert snapshot.document_route
    assert snapshot.document_route[0].accession == "0000080424-25-000012"
    assert snapshot.evidence
    assert snapshot.evidence[0].chunk_node_id.endswith("business-1-body")


def test_build_trajectory_from_state_accepts_serialized_repro_snapshot() -> None:
    trajectory = build_trajectory_from_state(
        normalize_trajectory_state(
            {
                "query": "Multi-filing question",
                "filing_set": [
                    {
                        "accession": "0000080424-25-000012",
                        "form_type": "10-K",
                        "filed_at": "2025-08-01",
                        "period_end": "2025-06-30",
                        "cik": "0000080424",
                    },
                    {
                        "accession": "0000080424-24-000010",
                        "form_type": "10-K",
                        "filed_at": "2024-08-01",
                        "period_end": "2024-06-30",
                        "cik": "0000080424",
                    },
                ],
                "graph_traversal": [
                    {"node_id": "doc-0000080424-25-000012", "stage": "macro", "edge_type": "CONTAINS"}
                ],
                "evidence_chunks": [
                    {
                        "chunk_node_id": "doc-0000080424-25-000012-html-item7-1-body",
                        "content_hash": "h1",
                        "source_type": "html",
                    }
                ],
            }
        )
    )
    assert len(trajectory.evidence) == 1
    assert trajectory.evidence[0].accession == "0000080424-25-000012"
