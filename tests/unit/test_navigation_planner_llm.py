"""Navigation planner live LLM path uses traced_llm_invoke correctly."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from evaluation.fixtures.navigation_eval_snapshot import build_navigation_eval_snapshot
from graph.query_api import LocalGraphQueryAPI
from graph.store import save_snapshot
from models.enums import GraphEdgeType
from retrieval.navigation.models import NavigationStage
from retrieval.navigation.planner import propose_next_hop


def test_propose_next_hop_live_calls_traced_llm_invoke(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_MOCK_LLM", "0")
    snap = build_navigation_eval_snapshot()
    save_snapshot(snap, tmp_path)
    api = LocalGraphQueryAPI(tmp_path, snap.issuer_id)
    root = next(n for n in snap.nodes if n.node_type.value == "DOCUMENT")

    fake_resp = MagicMock()
    fake_resp.content = '{"candidates":[],"intent_note":"test"}'

    with patch("retrieval.navigation.planner.create_chat_llm") as mock_llm_factory:
        with patch("retrieval.navigation.planner.traced_llm_invoke") as mock_trace:
            mock_llm_factory.return_value = MagicMock()
            mock_trace.return_value = (fake_resp, {})
            propose_next_hop(
                stage=NavigationStage.MESO,
                query="risk factors MD&A",
                snapshot_id=snap.snapshot_id,
                source_node_id=root.node_id,
                graph_api=api,
                prior_visits=[],
                filing_set=list(snap.manifest.filing_refs),
            )
            mock_trace.assert_called_once()
            args, kwargs = mock_trace.call_args
            assert args[0] == "navigation_meso"
            assert kwargs == {}
