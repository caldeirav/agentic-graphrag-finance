from models.enums import QueryStatus
from models.query import MacroPlan, TemporalScope
from tracing.mlflow_langgraph import build_trajectory_from_state


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
