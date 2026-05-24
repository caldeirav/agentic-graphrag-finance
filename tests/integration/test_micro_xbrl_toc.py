"""Integration: TOC micro collects XBRL fact chunks (not only -body suffix)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from graph.query_api import LocalGraphQueryAPI
from graph.store import load_snapshot
from models.enums import IntentSource, QueryIntent, SourceBias
from models.query import IntentRouterTrace
from retrieval.navigation.scope import chunk_ids_in_section_subtree
from retrieval.navigation.walker import run_meso_navigation, run_micro_navigation

_AAPL_SNAPSHOT = Path("data/graphs/AAPL/dd81bf32-7bdb-4414-b2b7-ce93bea04b7b")


@pytest.mark.skipif(os.environ.get("USE_MOCK_LLM", "1") != "1", reason="mock")
@pytest.mark.skipif(not _AAPL_SNAPSHOT.parent.exists(), reason="materialized AAPL graph required")
def test_micro_toc_scores_xbrl_fact_chunks(tmp_path):
    snap = load_snapshot("AAPL", "dd81bf32-7bdb-4414-b2b7-ce93bea04b7b", Path("data/graphs"))
    api = LocalGraphQueryAPI(Path("data/graphs"), "AAPL")
    ref = next(f for f in snap.manifest.filing_refs if f.accession == "0000320193-25-000079")
    sec = "doc-0000320193-25-000079-xbrl-facts"
    subtree = chunk_ids_in_section_subtree(snap, sec)
    assert any("xbrl-" in cid and not cid.endswith("-body") for cid in subtree)
    state = {
        "query": "What was total net sales in the most recent fiscal year?",
        "snapshot_id": snap.snapshot_id,
        "filing_set": [ref],
        "intent_trace": IntentRouterTrace(
            query_intent=QueryIntent.NUMERIC,
            intent_source=IntentSource.KEYWORD_FALLBACK,
            source_bias_applied=SourceBias.XBRL_PRIMARY,
            router_model_id="test",
            router_latency_ms=0,
        ),
    }
    state.update(run_meso_navigation(state, graph_api=api))
    micro = run_micro_navigation(state, graph_api=api)
    chunks = micro.get("evidence_chunks") or []
    assert chunks
    assert any(
        "RevenueFromContract" in c.excerpt or "Revenue" in c.excerpt
        for c in chunks
    )
