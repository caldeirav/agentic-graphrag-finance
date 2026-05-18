"""End-to-end pipeline: fetch → parse → graph → query."""

from __future__ import annotations

import json
import time
from pathlib import Path

from contracts.query import QueryRequest
from graph.builder import build_snapshot
from graph.store import save_snapshot
from ingestion import fetch_filing
from models.ingestion import CLIAskRequest, CLIAskResult
from parsing.sec_download_adapter import parse_from_cache, write_parsed_document
from retrieval.service import QueryService
from tracing.mlflow_langgraph import setup_mlflow


def _ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def run_ask_pipeline(request: CLIAskRequest) -> CLIAskResult:
    timings: dict[str, int] = {}
    ident = request.identifier
    form = request.form_types[0] if request.form_types else "10-K"

    t0 = time.perf_counter()
    entry = fetch_filing(
        ticker=ident.ticker,
        cik=ident.cik,
        accession=ident.accession,
        form_type=form,
        force_refresh=request.force_refresh,
    )
    timings["fetch"] = _ms(t0)

    t1 = time.perf_counter()
    doc = parse_from_cache(entry, use_docling=False)
    write_parsed_document(doc, Path("data/parsed"), ticker=ident.ticker)
    timings["parse"] = _ms(t1)

    t2 = time.perf_counter()
    issuer = ident.ticker.upper() if ident.ticker else doc.filing.cik
    snapshot = build_snapshot(issuer, [doc], snapshot_id=request.snapshot_id)
    save_snapshot(snapshot, Path("data/graphs"))
    timings["graph"] = _ms(t2)

    t3 = time.perf_counter()
    import mlflow

    setup_mlflow()
    svc = QueryService(graph_base_dir=Path("data/graphs"), issuer_id=issuer)
    resp = svc.answer(
        QueryRequest(
            query=request.query,
            snapshot_id=snapshot.snapshot_id,
            metadata={
                "issuer_id": issuer,
                "ticker": ident.ticker or "",
                "accession": doc.filing.accession,
            },
        )
    )
    mlflow_run_id = resp.mlflow_run_id
    if mlflow.active_run():
        mlflow.set_tags(
            {
                "ticker": ident.ticker or "",
                "accession": doc.filing.accession,
                "cik": doc.filing.cik,
            }
        )
    timings["query"] = _ms(t3)

    answer = resp.answer
    return CLIAskResult(
        answer_text=answer.text if answer else "",
        status=str(resp.status),
        mlflow_run_id=mlflow_run_id,
        snapshot_id=snapshot.snapshot_id,
        filings_used=[],
        timings_ms=timings,
        citations_count=len(answer.citations) if answer else 0,
    )


def run_test_pipeline(
    *,
    ticker: str | None = None,
    cik: str | None = None,
    accession: str | None = None,
    form_type: str = "10-K",
    force_refresh: bool = False,
    min_sections: int = 1,
    min_chunk_tables: int = 0,
    check_registry: bool = False,
) -> dict:
    from models.ingestion import CLITestResult

    entry = fetch_filing(
        ticker=ticker,
        cik=cik,
        accession=accession,
        form_type=form_type,
        force_refresh=force_refresh,
    )
    doc = parse_from_cache(entry, use_docling=False)
    issuer = ticker.upper() if ticker else doc.filing.cik
    snapshot = build_snapshot(issuer, [doc])
    messages: list[str] = []
    node_counts = {
        "sections": len(doc.sections),
        "tables": len(doc.tables),
        "graph_nodes": len(snapshot.nodes),
    }
    passed = node_counts["sections"] >= min_sections and node_counts["tables"] >= min_chunk_tables
    if not passed:
        messages.append(
            f"Thresholds not met: sections>={min_sections}, tables>={min_chunk_tables}"
        )

    if check_registry:
        reg_path = Path("specs/002-live-disclosure-cli/contracts/cli-test-registry.json")
        if reg_path.exists():
            reg = json.loads(reg_path.read_text())
            min_sections = max(min_sections, int(reg.get("min_sections", 1)))
            min_chunk_tables = max(min_chunk_tables, int(reg.get("min_chunk_tables", 0)))
            passed = (
                node_counts["sections"] >= min_sections
                and node_counts["tables"] >= min_chunk_tables
            )

    result = CLITestResult(
        passed=passed,
        node_counts=node_counts,
        cache_entry_path=str(entry.local_path),
        messages=messages,
    )
    return result.model_dump()
