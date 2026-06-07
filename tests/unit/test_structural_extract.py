"""Unit tests for structural extraction from trajectories (015)."""

from evaluation.reproduction.structural_extract import (
    extract_used_accessions,
    extract_visited_paths,
)


def test_extract_accessions_from_doc_chunk_ids() -> None:
    snap = {
        "evidence_chunks": [
            {"chunk_node_id": "doc-0000320193-24-000123-html-risk_factors-1-body"},
        ],
        "graph_traversal": [{"node_id": "doc-0000320193-24-000076-html-item1"}],
    }
    used = extract_used_accessions(snap)
    assert "0000320193-24-000123" in used
    assert "0000320193-24-000076" in used


def test_extract_visited_paths_from_traversal() -> None:
    snap = {
        "graph_traversal": [
            {"node_id": "doc-0000320193-24-000123-html-risk_factors"},
            {"to_node_id": "doc-0000320193-24-000123-xbrl-revenue"},
        ],
    }
    paths = extract_visited_paths(snap)
    assert "doc-0000320193-24-000123-html-risk_factors" in paths
    assert "doc-0000320193-24-000123-xbrl-revenue" in paths
