"""MLflow setup and trajectory artifacts."""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import mlflow
import yaml

from models.query import TrajectoryRecord


def load_mlflow_config(config_path: Path | None = None) -> dict:
    path = config_path or Path("configs/mlflow.yaml")
    if not path.exists():
        return {"tracking_uri": "./mlruns", "experiment_name": "sec-disclosure-rag"}
    return yaml.safe_load(path.read_text()) or {}


def _resolve_tracking_uri(cfg: dict) -> str:
    """Prefer MLFLOW_TRACKING_URI env; ignore bash-style placeholders in YAML."""
    uri = os.environ.get("MLFLOW_TRACKING_URI") or cfg.get("tracking_uri", "./mlruns")
    if isinstance(uri, str) and uri.startswith("${"):
        return "./mlruns"
    return uri


def setup_mlflow() -> str:
    cfg = load_mlflow_config()
    uri = _resolve_tracking_uri(cfg)
    mlflow.set_tracking_uri(uri)
    experiment = cfg.get("experiment_name", "sec-disclosure-rag")
    mlflow.set_experiment(experiment)
    if cfg.get("autolog_langchain", True):
        try:
            mlflow.langchain.autolog()
        except Exception:
            pass
    return uri


@contextmanager
def traced_query_run(
    query: str,
    snapshot_id: str,
    *,
    run_name: str | None = None,
    nested: bool = False,
) -> Generator[str, None, None]:
    setup_mlflow()
    with mlflow.start_run(
        run_name=run_name or f"query-{snapshot_id[:8]}",
        nested=nested,
    ):
        mlflow.log_params({"query": query[:500], "snapshot_id": snapshot_id})
        run = mlflow.active_run()
        run_id = run.info.run_id if run else ""
        yield run_id


def log_trajectory(run_id: str, trajectory: TrajectoryRecord) -> str:
    setup_mlflow()
    client = mlflow.tracking.MlflowClient()
    path = "trajectory.json"
    client.log_dict(run_id, trajectory.model_dump(mode="json"), path)
    uri = mlflow.get_tracking_uri()
    return f"{uri}/runs/{run_id}/artifacts/{path}"


def build_trajectory_from_state(state: dict[str, Any]) -> TrajectoryRecord:
    from models.enums import QueryStatus
    from models.query import GraphVisit

    visits = [
        GraphVisit(node_id=v.get("node_id", ""), stage=v.get("stage", "meso"))
        for v in state.get("graph_traversal", [])
        if isinstance(v, dict)
    ]
    return TrajectoryRecord(
        plan=state.get("macro_plan"),
        document_route=state.get("filing_set") or [],
        graph_traversal=visits,
        evidence=state.get("evidence_chunks") or [],
        status=state.get("status", QueryStatus.SUCCESS),
    )
