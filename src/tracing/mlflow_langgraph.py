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

_DEFAULT_TRACKING_URI = "sqlite:///mlflow.db"
_CONFIGURED = False

# Legacy bash-style defaults and broken paths that must never be used as URIs.
_INVALID_MARKERS = ("${", "mlruns}", ":-./mlruns", "MLFLOW_TRACKING_URI")


def load_mlflow_config(config_path: Path | None = None) -> dict:
    path = config_path or Path("configs/mlflow.yaml")
    if not path.exists():
        return {"tracking_uri": _DEFAULT_TRACKING_URI, "experiment_name": "sec-disclosure-rag"}
    return yaml.safe_load(path.read_text()) or {}


def resolve_tracking_uri(cfg: dict | None = None) -> str:
    """Resolve a safe MLflow tracking URI (env > yaml > sqlite default)."""
    cfg = cfg or load_mlflow_config()
    raw = os.environ.get("MLFLOW_TRACKING_URI") or cfg.get("tracking_uri") or _DEFAULT_TRACKING_URI
    uri = str(raw).strip().strip('"').strip("'")

    if not uri or any(marker in uri for marker in _INVALID_MARKERS):
        return _DEFAULT_TRACKING_URI

    # Relative filesystem paths → absolute file:// URIs (avoids cwd-dependent ./mlruns folders)
    if uri.startswith("./") or uri == "mlruns":
        rel = uri[2:] if uri.startswith("./") else uri
        abs_path = (Path.cwd() / rel).resolve()
        return abs_path.as_uri()

    if uri.endswith("/mlruns") or uri.endswith("\\mlruns"):
        return Path(uri).resolve().as_uri()

    return uri


def configure_mlflow() -> str:
    """Idempotent: set tracking URI in os.environ and MLflow before any runs."""
    global _CONFIGURED
    uri = resolve_tracking_uri()
    os.environ["MLFLOW_TRACKING_URI"] = uri
    mlflow.set_tracking_uri(uri)
    cfg = load_mlflow_config()
    experiment = cfg.get("experiment_name", "sec-disclosure-rag")
    mlflow.set_experiment(experiment)
    if cfg.get("autolog_langchain", True):
        try:
            mlflow.langchain.autolog()
        except Exception:
            pass
    _CONFIGURED = True
    return uri


def setup_mlflow() -> str:
    """Configure MLflow if not already configured; return tracking URI."""
    if not _CONFIGURED:
        return configure_mlflow()
    return mlflow.get_tracking_uri()


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
