import json
from pathlib import Path

from models.trajectory import AgentTrajectorySnapshot

FIXTURE = Path("tests/fixtures/trajectory_validation/valid_complete.json")


def test_valid_complete_fixture_parses():
    data = json.loads(FIXTURE.read_text())
    snap = AgentTrajectorySnapshot.model_validate(data)
    assert snap.schema_version == "1.0.0"
    assert snap.query_id
    assert len(snap.document_route) == 1
    assert len(snap.evidence) == 1
