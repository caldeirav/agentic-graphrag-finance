"""agent-query ask subcommand."""

from __future__ import annotations

import json

import typer

from cli.pipeline import run_ask_pipeline
from ingestion.edgar_client import ResolutionError
from models.corpus import CorpusTemporalScope
from models.ingestion import CLIAskRequest, IssuerIdentifierInput


def _validate_identifiers(ticker: str | None, cik: str | None) -> None:
    if ticker and cik:
        from ingestion.edgar_client import normalize_cik, resolve_ticker

        resolved = resolve_ticker(ticker)
        if resolved != normalize_cik(cik):
            raise typer.BadParameter(
                f"Ticker {ticker} maps to CIK {resolved}, but --cik {cik} was provided"
            )


def _build_temporal_scope(
    anchor: str | None,
    period: list[str],
    compare: str | None,
) -> CorpusTemporalScope | None:
    compare_periods: list[str] = []
    if compare:
        compare_periods = [p.strip() for p in compare.split(",") if p.strip()]
    if not anchor and not period and not compare_periods:
        return None
    return CorpusTemporalScope(
        anchor=anchor,
        periods=period,
        compare_periods=compare_periods,
    )


def ask(
    query: str = typer.Option(..., "--query", "-q", help="Natural language question"),
    ticker: str | None = typer.Option(None, "--ticker", "-t"),
    cik: str | None = typer.Option(None, "--cik"),
    accession: str | None = typer.Option(None, "--accession", "-a"),
    form: str = typer.Option("10-K", "--form", "-f"),
    force_refresh: bool = typer.Option(False, "--force-refresh"),
    snapshot_id: str | None = typer.Option(None, "--snapshot-id"),
    anchor: str | None = typer.Option(
        None, "--anchor", help="e.g. latest-annual, prior-quarter, latest-quarter"
    ),
    period: list[str] = typer.Option([], "--period", help="Fiscal period label e.g. FY2024-Q3"),
    compare: str | None = typer.Option(
        None, "--compare", help="Comma-separated fiscal periods to compare"
    ),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    if not ticker and not cik and not accession:
        raise typer.BadParameter("Provide --ticker, --cik, or --accession")
    try:
        _validate_identifiers(ticker, cik)
    except ResolutionError as exc:
        raise typer.BadParameter(str(exc)) from exc

    temporal = _build_temporal_scope(anchor, period, compare)
    if accession and temporal and (temporal.anchor or temporal.periods or temporal.compare_periods):
        raise typer.BadParameter(
            "Cannot combine --accession with --anchor, --period, or --compare temporal flags"
        )

    request = CLIAskRequest(
        identifier=IssuerIdentifierInput(ticker=ticker, cik=cik, accession=accession),
        query=query,
        form_types=[form],
        force_refresh=force_refresh,
        reuse_snapshot_id=snapshot_id,
        temporal_scope=temporal,
    )
    try:
        result = run_ask_pipeline(request)
    except Exception as exc:
        msg = str(exc)
        if "Connection error" in msg or "ConnectError" in type(exc).__name__:
            typer.echo(
                "Error: Could not reach the LLM API. "
                "Start LM Studio, load the model, enable the local server, "
                "and verify LM_STUDIO_BASE_URL in .env (default http://localhost:1234/v1).",
                err=True,
            )
        else:
            typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if as_json:
        typer.echo(json.dumps(result.model_dump(), indent=2, default=str))
        return

    typer.echo(result.answer_text)
    typer.echo(f"\nStatus: {result.status}")
    typer.echo(f"Snapshot: {result.snapshot_id}")
    typer.echo(f"MLflow run: {result.mlflow_run_id}")
    typer.echo(f"Citations: {result.citations_count}")
    if result.timings_ms:
        typer.echo("Timings (ms): " + ", ".join(f"{k}={v}" for k, v in result.timings_ms.items()))
    if result.snapshot_scope:
        scope = result.snapshot_scope
        typer.echo("\n--- Snapshot scope ---")
        typer.echo(f"Snapshot version: {scope.snapshot_id}")
        if scope.stale_snapshot:
            typer.echo("Stale: yes (newer filings available on EDGAR)")
        typer.echo("Bound:")
        for b in scope.bound_filings:
            typer.echo(f"  - {b.fiscal_period.label} ({b.form_type}) accession {b.accession}")
        if scope.newer_available:
            typer.echo("Newer available (not in snapshot):")
            for b in scope.newer_available:
                typer.echo(f"  - {b.fiscal_period.label} ({b.form_type}) accession {b.accession}")
        if scope.resolution_notes:
            typer.echo("Notes: " + "; ".join(scope.resolution_notes))
