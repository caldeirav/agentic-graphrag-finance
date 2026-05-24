"""Integration: TOC planner meso + scoped micro (009 A/C)."""

from __future__ import annotations

import os

import pytest

from evaluation.fixtures.navigation_eval_snapshot import build_navigation_eval_snapshot
from graph.query_api import LocalGraphQueryAPI
from graph.store import save_snapshot
from models.enums import IntentSource, QueryIntent, SourceBias
from models.query import IntentRouterTrace
from retrieval.navigation.walker import run_meso_navigation, run_micro_navigation


@pytest.mark.skipif(os.environ.get("USE_MOCK_LLM", "1") != "1", reason="mock")
def test_meso_toc_mda_query_scoped_micro(tmp_path):
    snap = build_navigation_eval_snapshot()
    save_snapshot(snap, tmp_path)
    api = LocalGraphQueryAPI(tmp_path, snap.issuer_id)
    ref = snap.manifest.filing_refs[0]
    state = {
        "query": "What are the principal risk factors discussed in management discussion and analysis?",
        "snapshot_id": snap.snapshot_id,
        "filing_set": [ref],
        "intent_trace": IntentRouterTrace(
            query_intent=QueryIntent.QUALITATIVE,
            intent_source=IntentSource.KEYWORD_FALLBACK,
            source_bias_applied=SourceBias.HTML_PRIMARY,
            router_model_id="test",
            router_latency_ms=0,
        ),
    }
    meso = run_meso_navigation(state, graph_api=api)
    trace = meso["navigation_trace"]
    assert trace.section_discovery_mode == "toc_planner"
    assert trace.toc_plans
    candidates = meso.get("section_candidates") or []
    assert candidates
    assert all("md_and_a" in c.section_node_id for c in candidates)

    state.update(meso)
    micro = run_micro_navigation(state, graph_api=api)
    chunks = micro.get("evidence_chunks") or []
    assert chunks
    assert len(chunks) >= 1
    for chunk in chunks:
        sid = chunk.section_id.lower()
        assert "risk_factors" not in sid
        assert "md_and_a" in sid or "mda" in sid
    from retrieval.context_budget import compact_evidence_for_llm

    compact = compact_evidence_for_llm(
        chunks,
        query=state["query"],
        query_intent=QueryIntent.QUALITATIVE,
    )
    assert compact
    assert any("md_and_a" in c.section_id for c in compact)
