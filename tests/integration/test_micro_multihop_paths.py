"""Integration: section → table → footnote multihop micro paths (009 US2)."""

from __future__ import annotations

import os

import pytest

from evaluation.fixtures.navigation_eval_snapshot import build_navigation_eval_snapshot
from graph.query_api import LocalGraphQueryAPI
from graph.store import save_snapshot
from retrieval.navigation.walker import run_meso_navigation, run_micro_navigation


@pytest.mark.skipif(os.environ.get("USE_MOCK_LLM", "1") != "1", reason="mock LLM")
def test_micro_multihop_table_to_footnote(tmp_path):
    snap = build_navigation_eval_snapshot()
    save_snapshot(snap, tmp_path)
    api = LocalGraphQueryAPI(tmp_path, snap.issuer_id)
    ref = snap.manifest.filing_refs[0]
    state = {
        "query": "What does the footnote say about revenue recognition?",
        "snapshot_id": snap.snapshot_id,
        "filing_set": [ref],
    }
    meso = run_meso_navigation(state, graph_api=api)
    state.update(meso)
    micro = run_micro_navigation(state, graph_api=api)
    trace = micro.get("navigation_trace")
    assert trace is not None
    fn_id = "doc-0000320193-24-000123-fn-rev"
    chunk_ids = {c.chunk_node_id for c in micro.get("evidence_chunks") or []}
    assert fn_id in chunk_ids or any(fn_id in p.chunk_node_ids for p in trace.micro_paths)
    matched = False
    for path in trace.micro_paths:
        seq = path.edge_type_sequence
        if "FOOTNOTE_OF" in seq or fn_id in path.chunk_node_ids:
            matched = True
            break
    assert matched
