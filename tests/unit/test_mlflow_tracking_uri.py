import os
from pathlib import Path

import pytest

import tracing.mlflow_langgraph as mlflow_mod
from tracing.mlflow_langgraph import configure_mlflow, resolve_tracking_uri


@pytest.fixture(autouse=True)
def _reset_mlflow_configured():
    prev = mlflow_mod._CONFIGURED
    mlflow_mod._CONFIGURED = False
    yield
    mlflow_mod._CONFIGURED = prev


def test_yaml_has_no_bash_placeholders():
    text = Path("configs/mlflow.yaml").read_text()
    assert "${" not in text


@pytest.mark.parametrize(
    "raw,expected_prefix",
    [
        ("${MLFLOW_TRACKING_URI:-./mlruns}", "sqlite:"),
        ("${MLFLOW_TRACKING_URI:-./mlruns}/0", "sqlite:"),
        ("", "sqlite:"),
        ("./mlruns", "file:"),
        ("sqlite:///mlflow.db", "sqlite:"),
    ],
)
def test_resolve_tracking_uri_rejects_placeholders(raw, expected_prefix, monkeypatch):
    monkeypatch.setenv("MLFLOW_TRACKING_URI", raw)
    uri = resolve_tracking_uri()
    assert uri.startswith(expected_prefix)
    assert "${" not in uri
    assert "mlruns}" not in uri


def test_configure_mlflow_sets_env(monkeypatch):
    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
    uri = configure_mlflow()
    assert os.environ["MLFLOW_TRACKING_URI"] == uri
    assert "${" not in uri
