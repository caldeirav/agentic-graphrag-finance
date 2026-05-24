from models.enums import QueryStatus
from models.query import MacroPlan, TemporalScope
from tracing.mlflow_langgraph import build_trajectory_from_state
from tracing.trajectory_export import build_agent_trajectory_snapshot


def test_agent_snapshot_has_schema_version():
    state = {
        "query_id": "q-1",
        "query": "test",
        "macro_plan": MacroPlan(
            intent_summary="test",
            temporal_scope=TemporalScope(anchor_periods=[]),
        ),
        "filing_set": [],
        "graph_traversal": [],
        "evidence_chunks": [],
        "status": QueryStatus.SUCCESS,
    }
    snap = build_agent_trajectory_snapshot(state)
    assert snap.schema_version == "1.0.0"
    assert snap.query_id == "q-1"


def test_trajectory_has_mandatory_fields():
    state = {
        "macro_plan": MacroPlan(
            intent_summary="test",
            temporal_scope=TemporalScope(anchor_periods=[]),
        ),
        "filing_set": [],
        "graph_traversal": [{"node_id": "sec-1", "stage": "meso"}],
        "evidence_chunks": [],
        "status": QueryStatus.SUCCESS,
    }
    traj = build_trajectory_from_state(state)
    assert traj.plan is not None
    assert isinstance(traj.graph_traversal, list)
