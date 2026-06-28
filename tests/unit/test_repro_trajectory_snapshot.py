"""Unit: QueryService always attaches trajectory_snapshot (023 M1 / SC-004)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from contracts.query import QueryRequest
from graph.store import save_snapshot
from models.enums import QueryStatus
from models.query import AnswerPackage, MacroPlan, TemporalScope
from retrieval.service import QueryService


def test_answer_always_includes_trajectory_snapshot(tmp_path, sample_graph_snapshot) -> None:
    save_snapshot(sample_graph_snapshot, tmp_path)
    svc = QueryService(graph_base_dir=tmp_path, issuer_id=sample_graph_snapshot.issuer_id)

    mock_result = {
        "query_id": "q-test",
        "snapshot_id": sample_graph_snapshot.snapshot_id,
        "issuer_id": sample_graph_snapshot.issuer_id,
        "query": "What is revenue?",
        "status": QueryStatus.SUCCESS,
        "answer": AnswerPackage(text="Revenue was $100.", citations=[]),
        "filing_set": [],
        "evidence_chunks": [],
        "macro_plan": MacroPlan(
            intent_summary="test",
            temporal_scope=TemporalScope(anchor_periods=[]),
        ),
        "graph_traversal": [],
        "synthesis_path": "computed_numeric",
    }
    mock_snapshot = MagicMock()
    mock_snapshot.model_dump.return_value = {
        "schema_version": "1.0.0",
        "query_id": "q-test",
        "synthesis_path": "computed_numeric",
    }

    with patch("retrieval.service.build_agent_graph") as build_graph:
        mock_compiled = MagicMock()
        mock_compiled.invoke.return_value = mock_result
        build_graph.return_value = mock_compiled
        with patch(
            "retrieval.service.build_agent_trajectory_snapshot",
            return_value=mock_snapshot,
        ):
            with patch("retrieval.service.traced_query_run") as traced:
                traced.return_value.__enter__ = MagicMock(return_value="")
                traced.return_value.__exit__ = MagicMock(return_value=False)
                with patch("retrieval.service.build_trajectory_from_state") as build_traj:
                    build_traj.return_value = MagicMock()
                    with patch("retrieval.service.run_post_query_audit") as audit:
                        audit.return_value = None
                        resp = svc.answer(
                            QueryRequest(
                                query="What is revenue?",
                                snapshot_id=sample_graph_snapshot.snapshot_id,
                                metadata={"defer_judge": "false"},
                            )
                        )

    assert resp.trajectory_snapshot is not None
    assert resp.trajectory_snapshot.get("synthesis_path") == "computed_numeric"
