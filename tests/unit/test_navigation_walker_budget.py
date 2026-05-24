"""Walker budget exhaustion tests."""

from __future__ import annotations

import os

import pytest

from graph.query_api import LocalGraphQueryAPI
from graph.store import save_snapshot
from retrieval.orchestration.nodes.meso_router import meso_router


@pytest.mark.skipif(os.environ.get("USE_MOCK_LLM", "1") != "1", reason="mock")
def test_meso_respects_low_visit_budget(tmp_path, sample_graph_snapshot, monkeypatch):
    import retrieval.navigation.walker as walker_mod

    def _tiny_budget():
        from retrieval.navigation.budget import NavigationBudgetLimits, NavigationBudgetState

        return NavigationBudgetState(
            limits=NavigationBudgetLimits(
                meso_max_hops_per_filing=1,
                meso_max_visits_per_filing=1,
                query_max_total_visits=2,
            )
        )

    monkeypatch.setattr(walker_mod, "load_navigation_budget", _tiny_budget)
    save_snapshot(sample_graph_snapshot, tmp_path)
    api = LocalGraphQueryAPI(tmp_path, sample_graph_snapshot.issuer_id)
    ref = sample_graph_snapshot.manifest.filing_refs[0]
    out = meso_router(
        {
            "query": "risk factors",
            "snapshot_id": sample_graph_snapshot.snapshot_id,
            "filing_set": [ref],
        },
        graph_api=api,
    )
    trace = out.get("navigation_trace")
    assert trace is not None
