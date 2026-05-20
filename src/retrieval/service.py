"""Public QueryService façade."""

from __future__ import annotations

from pathlib import Path

from contracts.query import QueryRequest, QueryResponse
from graph.query_api import LocalGraphQueryAPI
from models.enums import QueryStatus
from retrieval.orchestration.graph import build_agent_graph
from tracing.mlflow_langgraph import (
    build_trajectory_from_state,
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

        initial = {
            "query": request.query,
            "snapshot_id": request.snapshot_id,
            "temporal_anchor": request.metadata.get("temporal_anchor", ""),
            "filing_set": list(request.pre_bound_filings),
            "section_candidates": [],
            "evidence_chunks": [],
            "graph_traversal": [],
        }

        nested = __import__("mlflow").active_run() is not None
        with traced_query_run(request.query, request.snapshot_id, nested=nested) as run_id:
            result = compiled.invoke(initial)
            trajectory = build_trajectory_from_state(result)
            traj_uri = log_trajectory(run_id, trajectory) if run_id else ""

        status = result.get("status", QueryStatus.SUCCESS)
        return QueryResponse(
            answer=result.get("answer"),
            status=status,
            mlflow_run_id=run_id,
            trajectory_uri=traj_uri,
        )
