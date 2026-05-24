import json
from pathlib import Path

import pytest

from evaluation.validator import validate_trajectory
from models.trajectory import AgentTrajectorySnapshot

MANIFEST = Path("tests/fixtures/trajectory_validation/manifest.json")


@pytest.mark.parametrize(
    "fixture_file,expected",
    [
        (entry["file"], entry["expected_status"])
        for entry in json.loads(MANIFEST.read_text())["fixtures"]
    ],
)
def test_validator_fixtures(fixture_file: str, expected: str):
    path = Path("tests/fixtures/trajectory_validation") / fixture_file
    snap = AgentTrajectorySnapshot.model_validate(json.loads(path.read_text()))
    result = validate_trajectory(snap)
    assert result.status.value == expected
