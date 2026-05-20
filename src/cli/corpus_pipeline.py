"""Multi-filing corpus materialize and ask orchestration."""

from __future__ import annotations

import time
from pathlib import Path

import mlflow

from contracts.query import QueryRequest
from graph.registry import (
    build_issuer_snapshot,
    get_latest_snapshot,
    probe_stale_filings,
)
from ingestion import fetch_filing
from ingestion.corpus import (
    default_corpus_definition,
    materialize_corpus_members,
)
from models.corpus import (
    BoundFilingEntry,
    CorpusDefinition,
    CorpusMaterializationJob,
    CorpusMemberStatus,
    SnapshotScopeManifest,
    infer_fiscal_year_end_month,
)
from models.ingestion import CLIAskRequest, CLIAskResult
from parsing.sec_download_adapter import parse_from_cache, write_parsed_document
from retrieval.service import QueryService
from retrieval.temporal import bind_filings_for_query
from tracing.mlflow_langgraph import log_binding_manifest, setup_mlflow


def _ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def _issuer_key(request: CLIAskRequest) -> str:
    ident = request.identifier
    return (ident.ticker or ident.cik or "UNKNOWN").upper()


def _load_parsed_docs(
    job: CorpusMaterializationJob,
    parsed_root: Path,
) -> list:
    from models.parsing import ParsedDocument

    docs: list[ParsedDocument] = []
    for member in job.members:
        if member.status != CorpusMemberStatus.INCLUDED:
            continue
        acc = member.resolution.accession
        path = parsed_root / member.resolution.ticker.upper() / f"{acc}.json"
        if path.exists():
            docs.append(ParsedDocument.model_validate_json(path.read_text()))
    return docs


def run_materialize_pipeline(
    definition: CorpusDefinition | None = None,
    *,
    ticker: str | None = None,
    cik: str | None = None,
    force_refresh: bool = False,
    graphs_dir: Path | None = None,
    parsed_dir: Path | None = None,
) -> CorpusMaterializationJob:
    issuer = (ticker or cik or "").upper() or (definition.issuer_id if definition else "UNKNOWN")
    defn = definition or default_corpus_definition(issuer, ticker=ticker)
    if ticker:
        defn = defn.model_copy(update={"issuer_id": ticker.upper()})

    job = materialize_corpus_members(defn, force_refresh=force_refresh)
    parsed_root = parsed_dir or Path("data/parsed")
    graphs_root = graphs_dir or Path("data/graphs")

    for member in job.members:
        if member.status != CorpusMemberStatus.INCLUDED:
            continue
        entry = fetch_filing(
            resolution=member.resolution,
            force_refresh=force_refresh,
        )
        doc = parse_from_cache(entry)
        write_parsed_document(doc, parsed_root, ticker=member.resolution.ticker)

    docs = _load_parsed_docs(job, parsed_root)
    if not docs:
        job.completed_at = job.completed_at
        return job

    snapshot = build_issuer_snapshot(
        defn.issuer_id,
        docs,
        base_dir=graphs_root,
        corpus_definition=defn,
    )
    job.snapshot_id = snapshot.snapshot_id
    return job


def _build_scope_manifest(
    snapshot_id: str,
    issuer_id: str,
    binding,
    *,
    stale: bool = False,
    newer: list | None = None,
    fiscal_year_end_month: int = 12,
) -> SnapshotScopeManifest:
    return SnapshotScopeManifest(
        snapshot_id=snapshot_id,
        issuer_id=issuer_id,
        bound_filings=[
            BoundFilingEntry.from_filing_ref(
                r,
                fiscal_year_end_month=fiscal_year_end_month,
            )
            for r in binding.bound_filings
        ],
        stale_snapshot=stale,
        newer_available=[
            BoundFilingEntry.from_filing_ref(
                r,
                fiscal_year_end_month=fiscal_year_end_month,
            )
            for r in (newer or [])
        ],
        resolution_notes=binding.resolution_notes,
    )


def run_ask_pipeline(request: CLIAskRequest) -> CLIAskResult:
    timings: dict[str, int] = {}
    issuer = _issuer_key(request)
    graphs_root = Path("data/graphs")

    t0 = time.perf_counter()
    snapshot = None
    if request.reuse_snapshot_id:
        from graph.store import load_snapshot

        snapshot = load_snapshot(issuer, request.reuse_snapshot_id, graphs_root)
    else:
        snapshot = get_latest_snapshot(issuer, graphs_root)
        if snapshot is None:
            defn = request.corpus_definition or default_corpus_definition(
                issuer, ticker=request.identifier.ticker
            )
            job = run_materialize_pipeline(defn, force_refresh=request.force_refresh)
            if job.snapshot_id:
                from graph.store import load_snapshot

                snapshot = load_snapshot(issuer, job.snapshot_id, graphs_root)
    timings["materialize"] = _ms(t0)

    if snapshot is None:
        raise RuntimeError(f"No graph snapshot available for issuer {issuer}")

    scope = request.temporal_scope
    binding = bind_filings_for_query(scope, snapshot, query=request.query)

    if scope and not binding.bound_filings and (
        scope.anchor or scope.periods or scope.compare_periods
    ):
        t_ext = time.perf_counter()
        defn = request.corpus_definition or default_corpus_definition(
            issuer, ticker=request.identifier.ticker
        )
        job = run_materialize_pipeline(defn, force_refresh=request.force_refresh)
        timings["extend"] = _ms(t_ext)
        if job.snapshot_id:
            from graph.store import load_snapshot

            snapshot = load_snapshot(issuer, job.snapshot_id, graphs_root)
            binding = bind_filings_for_query(scope, snapshot, query=request.query)

    newer = probe_stale_filings(snapshot, ticker=request.identifier.ticker)
    stale = bool(newer)
    fy_end = infer_fiscal_year_end_month(list(snapshot.manifest.filing_refs))
    scope_manifest = _build_scope_manifest(
        snapshot.snapshot_id,
        issuer,
        binding,
        stale=stale,
        newer=newer,
        fiscal_year_end_month=fy_end,
    )

    t3 = time.perf_counter()
    setup_mlflow()
    svc = QueryService(graph_base_dir=graphs_root, issuer_id=issuer)
    resp = svc.answer(
        QueryRequest(
            query=request.query,
            snapshot_id=snapshot.snapshot_id,
            pre_bound_filings=binding.bound_filings,
            metadata={
                "issuer_id": issuer,
                "ticker": request.identifier.ticker or "",
                "stale_snapshot": str(stale),
                "bound_accessions": ",".join(r.accession for r in binding.bound_filings),
            },
        )
    )
    run_id = resp.mlflow_run_id
    if run_id:
        log_binding_manifest(run_id, scope_manifest)
    timings["query"] = _ms(t3)

    if mlflow.active_run():
        mlflow.set_tags(
            {
                "ticker": request.identifier.ticker or "",
                "snapshot_id": snapshot.snapshot_id,
                "stale_snapshot": str(stale),
            }
        )

    answer = resp.answer
    from models.ingestion import FilingResolution

    filings_used = [
        FilingResolution(
            ticker=request.identifier.ticker or issuer,
            cik=r.cik,
            accession=r.accession,
            form_type=r.form_type,
            filed_at=r.filed_at,
            period_end=r.period_end,
            edgar_filing_url=r.source_uri,
        )
        for r in binding.bound_filings
    ]

    return CLIAskResult(
        answer_text=answer.text if answer else "",
        status=str(resp.status),
        mlflow_run_id=run_id,
        snapshot_id=snapshot.snapshot_id,
        filings_used=filings_used,
        timings_ms=timings,
        citations_count=len(answer.citations) if answer else 0,
        snapshot_scope=scope_manifest,
    )
