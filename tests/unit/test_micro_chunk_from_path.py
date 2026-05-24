"""Unit: evidence chunks map to terminal navigable chunk nodes (009 US2)."""

from __future__ import annotations

from evaluation.fixtures.navigation_eval_snapshot import build_navigation_eval_snapshot
from retrieval.navigation.validator import is_chunk_node
from retrieval.navigation.walker import run_meso_navigation, run_micro_navigation
from unittest.mock import MagicMock


def _in_memory_api(snap):
    api = MagicMock()
    api.get_snapshot.return_value = snap

    def _sections(snapshot_id, filings):
        accs = {f.accession for f in filings}
        doc_ids = {
            n.node_id
            for n in snap.nodes
            if n.node_type.value == "DOCUMENT"
            and any(a in n.node_id for a in accs)
        }
        out = []
        for edge in snap.edges:
            if edge.edge_type.value != "CONTAINS" or edge.source_id not in doc_ids:
                continue
            for n in snap.nodes:
                if n.node_id == edge.target_id and n.node_type.value == "SECTION":
                    out.append(n)
        return out

    api.sections_for_filings.side_effect = _sections
    api.document_roots_for_filings.side_effect = lambda sid, filings: [
        n
        for n in snap.nodes
        if n.node_type.value == "DOCUMENT"
    ]
    from graph.edge_catalog import STRUCTURAL_EDGE_TYPES

    def _outgoing(snapshot_id, node_id, edge_types):
        allowed = {e.value for e in edge_types if e.value in STRUCTURAL_EDGE_TYPES}
        out = []
        node_by_id = {n.node_id: n for n in snap.nodes}
        for edge in snap.edges:
            if edge.edge_type.value not in allowed:
                continue
            if edge.source_id == node_id and edge.target_id in node_by_id:
                out.append((edge.edge_type, node_by_id[edge.target_id]))
        return out

    api.outgoing_edges.side_effect = _outgoing
    api.navigable_node_count.return_value = 10
    return api


def test_evidence_chunks_are_terminal_chunk_nodes():
    snap = build_navigation_eval_snapshot()
    api = _in_memory_api(snap)
    ref = snap.manifest.filing_refs[0]
    state = {
        "query": "total net sales revenue",
        "snapshot_id": snap.snapshot_id,
        "filing_set": [ref],
    }
    state.update(run_meso_navigation(state, graph_api=api))
    micro = run_micro_navigation(state, graph_api=api)
    nodes = {n.node_id: n for n in snap.nodes}
    walked: set[str] = set()
    trace = micro.get("navigation_trace")
    if trace:
        for path in trace.micro_paths:
            walked.update(path.chunk_node_ids)
    for chunk in micro.get("evidence_chunks") or []:
        node = nodes[chunk.chunk_node_id]
        assert is_chunk_node(node.node_type)
        if walked:
            assert chunk.chunk_node_id in walked
