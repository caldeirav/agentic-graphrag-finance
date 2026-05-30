"""Mock judge guard for benchmark-dataset CLI (012)."""

import os
from pathlib import Path

import pytest
import typer

from cli.commands.benchmark_dataset import enforce_mock_judge_policy

REPO = Path(__file__).resolve().parents[2]
V1_CONFIG = REPO / "configs/benchmarks/custom_judge_v1.yaml"
CI_CONFIG = REPO / "configs/benchmarks/custom_judge_ci.yaml"


def test_mock_judge_rejected_for_production_config():
    with pytest.raises(typer.BadParameter, match="custom_judge_ci"):
        enforce_mock_judge_policy(V1_CONFIG, mock_judge=True)


def test_mock_judge_allowed_for_ci_config():
    enforce_mock_judge_policy(CI_CONFIG, mock_judge=True)


def test_use_mock_judge_env_rejected_for_production_config(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("USE_MOCK_JUDGE", "1")
    with pytest.raises(typer.BadParameter, match="custom_judge_ci"):
        enforce_mock_judge_policy(V1_CONFIG, mock_judge=False)
    monkeypatch.delenv("USE_MOCK_JUDGE", raising=False)
