"""agent-query materialize — build multi-filing issuer graph snapshot."""

from __future__ import annotations

import json

import typer

from cli.corpus_pipeline import run_materialize_pipeline
from ingestion.corpus import CorpusCapExceededError, default_corpus_definition
from ingestion.edgar_client import ResolutionError


def materialize(
    ticker: str | None = typer.Option(None, "--ticker", "-t"),
    cik: str | None = typer.Option(None, "--cik"),
    force_refresh: bool = typer.Option(False, "--force-refresh"),
    max_filings: int = typer.Option(12, "--max-filings"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    if not ticker and not cik:
        raise typer.BadParameter("Provide --ticker or --cik")
    issuer = (ticker or cik or "").upper()
    try:
        defn = default_corpus_definition(issuer, ticker=ticker)
        defn = defn.model_copy(update={"max_filings": max_filings})
        job = run_materialize_pipeline(defn, ticker=ticker, cik=cik, force_refresh=force_refresh)
    except CorpusCapExceededError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except ResolutionError as exc:
        raise typer.BadParameter(str(exc)) from exc

    from models.corpus import CorpusMemberStatus

    included = sum(1 for m in job.members if m.status == CorpusMemberStatus.INCLUDED)
    failed = sum(1 for m in job.members if m.status == CorpusMemberStatus.FAILED)
    payload = {
        "job_id": job.job_id,
        "snapshot_id": job.snapshot_id,
        "issuer_id": defn.issuer_id,
        "included": included,
        "failed": failed,
        "members": [
            {
                "accession": m.resolution.accession,
                "form_type": m.resolution.form_type,
                "status": m.status.value,
                "fiscal_period": m.fiscal_period.label if m.fiscal_period else "",
            }
            for m in job.members
        ],
    }
    if as_json:
        typer.echo(json.dumps(payload, indent=2))
        return
    typer.echo(f"Snapshot: {job.snapshot_id}")
    typer.echo(f"Issuer: {defn.issuer_id}")
    typer.echo(f"Included: {included}, Failed: {failed}")
    for m in job.members:
        fp = m.fiscal_period.label if m.fiscal_period else "?"
        typer.echo(f"  - {fp} {m.resolution.form_type} {m.resolution.accession} [{m.status.value}]")
