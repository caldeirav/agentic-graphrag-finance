"""Integration: graph-native meso navigation (009 US1)."""

from __future__ import annotations

import os

import pytest

from graph.query_api import LocalGraphQueryAPI
from graph.store import save_snapshot
from models.enums import IntentSource, QueryIntent, SourceBias
from models.query import IntentRouterTrace
from retrieval.orchestration.nodes.meso_router import meso_router


@pytest.mark.skipif(os.environ.get("USE_MOCK_LLM", "1") != "1", reason="mock LLM")
def test_meso_graph_navigation_within_scope(tmp_path, sample_graph_snapshot):
    save_snapshot(sample_graph_snapshot, tmp_path)
    api = LocalGraphQueryAPI(tmp_path, sample_graph_snapshot.issuer_id)
    ref = sample_graph_snapshot.manifest.filing_refs[0]
    state = {
        "query": "What are the risk factors in MD&A?",
        "snapshot_id": sample_graph_snapshot.snapshot_id,
        "filing_set": [ref],
        "intent_trace": IntentRouterTrace(
            query_intent=QueryIntent.QUALITATIVE,
            intent_source=IntentSource.KEYWORD_FALLBACK,
            source_bias_applied=SourceBias.HTML_PRIMARY,
            router_model_id="test",
            router_latency_ms=0,
        ),
    }
    out = meso_router(state, graph_api=api)
    candidates = out.get("section_candidates") or []
    assert len(candidates) <= 3
    trace = out.get("navigation_trace")
    assert trace is not None
    visits = out.get("graph_traversal") or []
    if visits:
        assert any(v.get("stage") == "meso" for v in visits)
        assert any(v.get("edge_type") for v in visits)
    for c in candidates:
        assert c.accession == ref.accession or not c.accession
        assert c.path
        if c.edge_types:
            assert c.edge_types[0] in ("CONTAINS", "NEXT", "FOOTNOTE_OF", "REFERENCES")
