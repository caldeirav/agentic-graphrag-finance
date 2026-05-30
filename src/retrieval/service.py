"""Public QueryService façade."""

from __future__ import annotations

import time
import uuid
from pathlib import Path

from contracts.query import QueryRequest, QueryResponse
from evaluation.ask_judge import run_post_query_audit
from graph.query_api import LocalGraphQueryAPI
from models.enums import QueryStatus
from models.reproduction import VariantCapabilities
from retrieval.orchestration.graph import build_agent_graph
from tracing.console_trace.audit import emit_trajectory_audit_footer
from tracing.console_trace.config import build_trace_run_config
from tracing.console_trace.context import set_trace_reporter
from tracing.console_trace.models import TraceLevel
from tracing.console_trace.reporter import ConsoleTraceReporter
from tracing.mlflow_langgraph import (
    build_trajectory_from_state,
    log_agent_trajectory,
    log_intent_router,
    log_macro_binding,
    log_navigation_trace,
    log_trajectory,
    traced_query_run,
)
from tracing.trajectory_export import build_agent_trajectory_snapshot


class QueryService:
    def __init__(
        self,
        graph_base_dir: Path | None = None,
        issuer_id: str | None = None,
    ) -> None:
        self._graph_base = graph_base_dir or Path("data/graphs")
        self._issuer_id = issuer_id

    def answer(self, request: QueryRequest) -> QueryResponse:
        issuer = self._issuer_id or request.metadata.get("issuer_id", "")
        if not issuer:
            snap_path = self._graph_base
            issuers = [p.name for p in snap_path.iterdir() if p.is_dir()]
            issuer = issuers[0] if issuers else "unknown"

        graph_api = LocalGraphQueryAPI(self._graph_base, issuer)
        variant_profile = VariantCapabilities(
            disable_macro_router=request.metadata.get("variant_disable_macro_router", "")
            .lower()
            in ("1", "true", "yes"),
            disable_graph_walker=request.metadata.get("variant_disable_graph_walker", "")
            .lower()
            in ("1", "true", "yes"),
            xbrl_only=request.metadata.get("variant_xbrl_only", "").lower()
            in ("1", "true", "yes"),
        )
        compiled = build_agent_graph(graph_api, variant_profile=variant_profile)

        trace_level_raw = request.metadata.get("trace_level", "")
        trace_level = TraceLevel(trace_level_raw) if trace_level_raw else TraceLevel.QUIET
        emit_jsonl = request.metadata.get("trace_json", "").lower() in ("1", "true", "yes")
        trace_config = build_trace_run_config(trace_level, emit_jsonl=emit_jsonl)
        reporter = ConsoleTraceReporter(trace_config)
        reporter.mark_run_start()
        set_trace_reporter(reporter)

        query_id = request.metadata.get("query_id") or str(uuid.uuid4())
        initial = {
            "query": request.query,
            "query_id": query_id,
            "snapshot_id": request.snapshot_id,
            "issuer_id": issuer,
            "temporal_anchor": request.metadata.get("temporal_anchor", ""),
            "filing_set": list(request.pre_bound_filings),
            "cli_prebound": request.metadata.get("cli_prebound", "").lower()
            in ("1", "true", "yes"),
            "binding_deferred": request.metadata.get("binding_deferred", "").lower()
            in ("1", "true", "yes"),
            "section_candidates": [],
            "evidence_chunks": [],
            "graph_traversal": [],
            "trace_config": trace_config,
            "variant_disable_macro_router": request.metadata.get(
                "variant_disable_macro_router", ""
            ).lower()
            in ("1", "true", "yes"),
            "variant_disable_graph_walker": request.metadata.get(
                "variant_disable_graph_walker", ""
            ).lower()
            in ("1", "true", "yes"),
            "variant_xbrl_only": request.metadata.get("variant_xbrl_only", "").lower()
            in ("1", "true", "yes"),
            "expected_section_paths_json": request.metadata.get("expected_section_paths", "[]"),
        }

        nested = __import__("mlflow").active_run() is not None
        t0 = time.perf_counter()
        run_id = ""
        result: dict = {}
        traj_uri = ""
        audit = None
        with traced_query_run(request.query, request.snapshot_id, nested=nested) as rid:
            run_id = rid or ""
            result = compiled.invoke(initial)
            result.setdefault("query_id", query_id)
            result.setdefault("snapshot_id", request.snapshot_id)
            result.setdefault("issuer_id", issuer)

            snapshot = build_agent_trajectory_snapshot(
                result,
                mlflow_run_id=run_id,
                issuer_id=issuer,
            )
            trajectory = build_trajectory_from_state(result)

            if run_id and result.get("macro_binding_record") is not None:
                log_macro_binding(run_id, result["macro_binding_record"])
            if run_id and result.get("navigation_trace") is not None:
                log_navigation_trace(run_id, result["navigation_trace"])
            if run_id and result.get("intent_trace") is not None:
                log_intent_router(run_id, result["intent_trace"])
            if run_id:
                traj_uri = log_agent_trajectory(run_id, snapshot)
                log_trajectory(run_id, trajectory)

            audit = run_post_query_audit(
                snapshot,
                result.get("answer"),
                question=request.query,
                mlflow_run_id=run_id,
            )
        if audit is not None and audit.judge_summary is not None:
            emit_trajectory_audit_footer(reporter, audit)

        answer = result.get("answer")
        reporter.write_summary(
            status=str(result.get("status", QueryStatus.SUCCESS)),
            citation_count=len(answer.citations) if answer else 0,
            total_ms=int((time.perf_counter() - t0) * 1000),
        )
        set_trace_reporter(None)

        status = result.get("status", QueryStatus.SUCCESS)
        judge_scores = {}
        if audit is not None and audit.judge_summary:
            judge_scores = {c.criterion_id: c.score for c in audit.judge_summary.criteria}
        return QueryResponse(
            answer=result.get("answer"),
            status=status,
            mlflow_run_id=run_id,
            trajectory_uri=traj_uri,
            query_id=query_id,
            validation_status=(
                audit.validation_status.value if audit is not None else ""
            ),
            judge_status=(
                audit.judge_summary.judge_status.value
                if audit is not None and audit.judge_summary
                else ""
            ),
            judge_scores=judge_scores,
        )
