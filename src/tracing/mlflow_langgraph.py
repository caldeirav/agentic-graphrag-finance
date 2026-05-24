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
from models.evaluation import JudgeRunSummary, TrajectoryValidationResult
from models.query import IntentRouterTrace, TrajectoryRecord
from models.trajectory import AgentTrajectorySnapshot
from tracing.trajectory_export import build_agent_trajectory_snapshot

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


def set_audit_run_tags(
    run_id: str,
    *,
    trajectory_schema_version: str | None = None,
    validation_status: str | None = None,
    judge_status: str | None = None,
    judge_weakest_criterion: str | None = None,
    judge_weakest_stage: str | None = None,
    judge_scores: dict[str, float] | None = None,
) -> None:
    setup_mlflow()
    tags: dict[str, str] = {}
    if trajectory_schema_version:
        tags["trajectory_schema_version"] = trajectory_schema_version
    if validation_status:
        tags["validation_status"] = validation_status
    if judge_status:
        tags["judge_status"] = judge_status
    if judge_weakest_criterion:
        tags["judge_weakest_criterion"] = judge_weakest_criterion
    if judge_weakest_stage:
        tags["judge_weakest_stage"] = judge_weakest_stage
    if judge_scores:
        for cid, score in judge_scores.items():
            tags[f"judge_score_{cid}"] = f"{score:.3f}"
    if tags and run_id:
        client = mlflow.tracking.MlflowClient()
        for k, v in tags.items():
            client.set_tag(run_id, k, v[:500])


def log_agent_trajectory(run_id: str, snapshot: AgentTrajectorySnapshot) -> str:
    setup_mlflow()
    client = mlflow.tracking.MlflowClient()
    path = "agent_trajectory.json"
    client.log_dict(run_id, snapshot.model_dump(mode="json"), path)
    set_audit_run_tags(run_id, trajectory_schema_version=snapshot.schema_version)
    uri = mlflow.get_tracking_uri()
    return f"{uri}/runs/{run_id}/artifacts/{path}"


def log_trajectory_validation(run_id: str, result: TrajectoryValidationResult) -> str:
    setup_mlflow()
    client = mlflow.tracking.MlflowClient()
    path = "evaluation/trajectory_validation.json"
    client.log_dict(run_id, result.model_dump(mode="json"), path)
    set_audit_run_tags(run_id, validation_status=result.status.value)
    uri = mlflow.get_tracking_uri()
    return f"{uri}/runs/{run_id}/artifacts/{path}"


def log_judge_verdict(run_id: str, summary: JudgeRunSummary) -> str:
    setup_mlflow()
    client = mlflow.tracking.MlflowClient()
    path = "evaluation/judge_verdict.json"
    client.log_dict(run_id, summary.model_dump(mode="json"), path)
    scores = {c.criterion_id: c.score for c in summary.criteria}
    set_audit_run_tags(
        run_id,
        judge_status=summary.judge_status.value,
        judge_weakest_criterion=summary.weakest_criterion_id,
        judge_weakest_stage=summary.weakest_stage,
        judge_scores=scores,
    )
    for cid, score in scores.items():
        client.log_metric(run_id, f"judge.{cid}", float(score))
    client.log_param(run_id, "judge_model", summary.judge_model[:250])
    client.log_param(run_id, "judge_status", summary.judge_status.value)
    if summary.weakest_criterion_id:
        client.log_param(run_id, "judge_weakest_criterion", summary.weakest_criterion_id[:250])
    uri = mlflow.get_tracking_uri()
    return f"{uri}/runs/{run_id}/artifacts/{path}"


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
    snapshot = build_agent_trajectory_snapshot(state)
    from models.query import GraphVisit

    visits = [
        GraphVisit(
            node_id=h.node_id,
            edge_id=h.edge_id,
            stage=h.stage,
            path_edge_types=[h.edge_type] if h.edge_type else [],
            path_node_ids=[],
        )
        for h in snapshot.graph_traversal
    ]
    from models.enums import EvidenceSourceType
    from models.query import EvidenceChunk

    evidence: list[EvidenceChunk] = []
    for e in snapshot.evidence:
        try:
            st = EvidenceSourceType(e.source_type.upper())
        except ValueError:
            st = EvidenceSourceType.NARRATIVE
        evidence.append(
            EvidenceChunk(
                chunk_node_id=e.chunk_node_id,
                excerpt="",
                content_hash=e.content_hash,
                citation_label=e.citation_label,
                source_type=st,
                accession=e.accession,
                section_id=e.section_id or "",
            )
        )
    macro_plan = state.get("macro_plan")
    filing_refs = list(state.get("filing_set") or [])
    return TrajectoryRecord(
        plan=macro_plan,
        macro_binding=snapshot.macro_binding,
        navigation_trace=snapshot.navigation_trace,
        intent_router=snapshot.intent_router,
        document_route=filing_refs,
        graph_traversal=visits,
        evidence=evidence or list(state.get("evidence_chunks") or []),
        status=snapshot.status,
    )
