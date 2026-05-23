"""Public QueryService façade."""

from __future__ import annotations

import time
from pathlib import Path

from contracts.query import QueryRequest, QueryResponse
from graph.query_api import LocalGraphQueryAPI
from models.enums import QueryStatus
from retrieval.orchestration.graph import build_agent_graph
from tracing.console_trace.config import build_trace_run_config
from tracing.console_trace.context import set_trace_reporter
from tracing.console_trace.models import TraceLevel
from tracing.console_trace.reporter import ConsoleTraceReporter
from tracing.mlflow_langgraph import (
    build_trajectory_from_state,
    log_intent_router,
    log_trajectory,
    traced_query_run,
)


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
        compiled = build_agent_graph(graph_api)

        trace_level_raw = request.metadata.get("trace_level", "")
        trace_level = TraceLevel(trace_level_raw) if trace_level_raw else TraceLevel.QUIET
        emit_jsonl = request.metadata.get("trace_json", "").lower() in ("1", "true", "yes")
        trace_config = build_trace_run_config(trace_level, emit_jsonl=emit_jsonl)
        reporter = ConsoleTraceReporter(trace_config)
        reporter.mark_run_start()
        set_trace_reporter(reporter)

        initial = {
            "query": request.query,
            "snapshot_id": request.snapshot_id,
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
        }

        nested = __import__("mlflow").active_run() is not None
        t0 = time.perf_counter()
        run_id = ""
        result: dict = {}
        try:
            with traced_query_run(request.query, request.snapshot_id, nested=nested) as rid:
                run_id = rid or ""
                result = compiled.invoke(initial)
        finally:
            answer = result.get("answer")
            reporter.write_summary(
                status=str(result.get("status", QueryStatus.SUCCESS)),
                citation_count=len(answer.citations) if answer else 0,
                total_ms=int((time.perf_counter() - t0) * 1000),
            )
            set_trace_reporter(None)

        trajectory = build_trajectory_from_state(result)
        if run_id and result.get("macro_binding_record") is not None:
            from tracing.mlflow_langgraph import log_macro_binding

            log_macro_binding(run_id, result["macro_binding_record"])
        if run_id and result.get("intent_trace") is not None:
            log_intent_router(run_id, result["intent_trace"])
        traj_uri = log_trajectory(run_id, trajectory) if run_id else ""

        status = result.get("status", QueryStatus.SUCCESS)
        return QueryResponse(
            answer=result.get("answer"),
            status=status,
            mlflow_run_id=run_id,
            trajectory_uri=traj_uri,
        )
