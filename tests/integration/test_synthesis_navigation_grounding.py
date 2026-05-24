"""Integration: synthesis evidence ⊆ graph-walked micro chunks (009 SC-005)."""

from __future__ import annotations

import os

import pytest

from evaluation.fixtures.navigation_eval_snapshot import build_navigation_eval_snapshot
from graph.query_api import LocalGraphQueryAPI
from graph.store import save_snapshot
from retrieval.navigation.walker import run_meso_navigation, run_micro_navigation
from retrieval.synthesis import synthesize


def _walked_chunk_ids(micro_out: dict) -> set[str]:
    trace = micro_out.get("navigation_trace")
    if trace is None:
        return set()
    ids: set[str] = set()
    for path in trace.micro_paths:
        ids.update(path.chunk_node_ids)
    return ids


@pytest.mark.skipif(os.environ.get("USE_MOCK_LLM", "1") != "1", reason="mock LLM")
def test_synthesis_uses_only_walked_chunks(tmp_path):
    snap = build_navigation_eval_snapshot()
    save_snapshot(snap, tmp_path)
    api = LocalGraphQueryAPI(tmp_path, snap.issuer_id)
    ref = snap.manifest.filing_refs[0]
    state = {
        "query": "What was total net sales?",
        "snapshot_id": snap.snapshot_id,
        "filing_set": [ref],
    }
    state.update(run_meso_navigation(state, graph_api=api))
    micro = run_micro_navigation(state, graph_api=api)
    state.update(micro)
    walked = _walked_chunk_ids(micro)
    assert walked
    syn = synthesize(state)
    for chunk in state.get("evidence_chunks") or []:
        assert chunk.chunk_node_id in walked
    assert syn.get("answer") is not None
