"""MLflow setup and trajectory artifacts."""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import mlflow
import yaml

from models.corpus import SnapshotScopeManifest
from models.query import IntentRouterTrace, TrajectoryRecord

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
    yaml_uri = str(cfg.get("tracking_uri") or _DEFAULT_TRACKING_URI).strip()
    raw = os.environ.get("MLFLOW_TRACKING_URI") or yaml_uri or _DEFAULT_TRACKING_URI
    uri = str(raw).strip().strip('"').strip("'")

    if not uri or any(marker in uri for marker in _INVALID_MARKERS):
        return _DEFAULT_TRACKING_URI

    # Legacy ./mlruns in env → prefer sqlite from configs/mlflow.yaml (project default).
    if uri in ("./mlruns", "mlruns") and yaml_uri.startswith("sqlite"):
        return yaml_uri

    # Other relative filesystem paths → absolute file:// URIs
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


def log_binding_manifest(run_id: str, manifest: SnapshotScopeManifest) -> str:
    setup_mlflow()
    client = mlflow.tracking.MlflowClient()
    path = "binding_manifest.json"
    client.log_dict(run_id, manifest.model_dump(mode="json"), path)
    bound = ",".join(b.accession for b in manifest.bound_filings)
    mlflow.set_tags(
        {
            "stale_snapshot": str(manifest.stale_snapshot).lower(),
            "bound_accessions": bound[:500],
        }
    )
    uri = mlflow.get_tracking_uri()
    return f"{uri}/runs/{run_id}/artifacts/{path}"


def log_reachability_report(run_id: str, report_path: Path) -> str:
    setup_mlflow()
    client = mlflow.tracking.MlflowClient()
    if report_path.exists():
        client.log_artifact(run_id, str(report_path), artifact_path="reachability")
    return str(report_path)


def log_intent_router(run_id: str, trace: IntentRouterTrace) -> str:
    setup_mlflow()
    client = mlflow.tracking.MlflowClient()
    params = {
        "query_intent": trace.query_intent.value,
        "intent_source": trace.intent_source.value,
        "source_bias_applied": trace.source_bias_applied.value,
    }
    if trace.router_fallback_reason is not None:
        params["router_fallback_reason"] = trace.router_fallback_reason.value
    mlflow.log_params(params)
    client.log_dict(run_id, trace.model_dump(mode="json"), "intent_router.json")
    uri = mlflow.get_tracking_uri()
    return f"{uri}/runs/{run_id}/artifacts/intent_router.json"


def log_trajectory(run_id: str, trajectory: TrajectoryRecord) -> str:
    setup_mlflow()
    client = mlflow.tracking.MlflowClient()
    path = "trajectory.json"
    client.log_dict(run_id, trajectory.model_dump(mode="json"), path)
    uri = mlflow.get_tracking_uri()
    return f"{uri}/runs/{run_id}/artifacts/{path}"


def log_navigation_trace(run_id: str, record: Any) -> str:
    setup_mlflow()
    client = mlflow.tracking.MlflowClient()
    payload = record.to_trajectory_dict() if hasattr(record, "to_trajectory_dict") else record
    path = "navigation_trace.json"
    client.log_dict(run_id, payload, path)
    uri = mlflow.get_tracking_uri()
    return f"{uri}/runs/{run_id}/artifacts/{path}"


def log_macro_binding(run_id: str, record: Any) -> str:
    setup_mlflow()
    client = mlflow.tracking.MlflowClient()
    payload = record.to_trajectory_dict() if hasattr(record, "to_trajectory_dict") else record
    path = "macro_binding.json"
    client.log_dict(run_id, payload, path)
    uri = mlflow.get_tracking_uri()
    return f"{uri}/runs/{run_id}/artifacts/{path}"


def build_trajectory_from_state(state: dict[str, Any]) -> TrajectoryRecord:
    from models.enums import QueryStatus
    from models.query import GraphVisit

    visits = []
    for v in state.get("graph_traversal", []):
        if not isinstance(v, dict):
            continue
        edge_types = list(v.get("path_edge_types") or [])
        if v.get("edge_type") and not edge_types:
            edge_types = [str(v.get("edge_type"))]
        visits.append(
            GraphVisit(
                node_id=v.get("node_id", ""),
                stage=v.get("stage", "meso"),
                path_edge_types=edge_types,
                path_node_ids=list(v.get("path_node_ids") or []),
            )
        )
    macro_binding = None
    record = state.get("macro_binding_record")
    if record is not None and hasattr(record, "to_trajectory_dict"):
        macro_binding = record.to_trajectory_dict()
    nav_trace = None
    nt = state.get("navigation_trace")
    if nt is not None:
        nav_trace = nt.to_trajectory_dict() if hasattr(nt, "to_trajectory_dict") else nt
    return TrajectoryRecord(
        plan=state.get("macro_plan"),
        macro_binding=macro_binding,
        navigation_trace=nav_trace,
        intent_router=state.get("intent_trace"),
        document_route=state.get("filing_set") or [],
        graph_traversal=visits,
        evidence=state.get("evidence_chunks") or [],
        status=state.get("status", QueryStatus.SUCCESS),
    )
