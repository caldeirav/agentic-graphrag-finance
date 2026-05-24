from evaluation.validator.trajectory import validate_trajectory
from models.evaluation import ValidationStatus
from models.trajectory import AgentTrajectorySnapshot, TrajectoryPlan


def _minimal(**kwargs) -> AgentTrajectorySnapshot:
    base = {
        "query_id": "q1",
        "query_text": "q",
        "plan": TrajectoryPlan(intent_summary="i", chosen_path_rationale="r"),
        "document_route": [],
        "graph_traversal": [],
        "evidence": [],
    }
    base.update(kwargs)
    return AgentTrajectorySnapshot.model_validate(base)


def test_missing_schema_version_incomplete():
    snap = _minimal(schema_version="")
    assert validate_trajectory(snap).status == ValidationStatus.INCOMPLETE
