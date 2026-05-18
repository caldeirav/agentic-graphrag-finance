"""agent-query ask subcommand."""

from __future__ import annotations

import json

import typer

from cli.pipeline import run_ask_pipeline
from ingestion.sec_client import ResolutionError
from models.ingestion import CLIAskRequest, IssuerIdentifierInput


def _validate_identifiers(ticker: str | None, cik: str | None) -> None:
    if ticker and cik:
        from ingestion.sec_client import _normalize_cik, resolve_ticker

        resolved = resolve_ticker(ticker)
        if resolved != _normalize_cik(cik):
            raise typer.BadParameter(
                f"Ticker {ticker} maps to CIK {resolved}, but --cik {cik} was provided"
            )


def ask(
    query: str = typer.Option(..., "--query", "-q", help="Natural language question"),
    ticker: str | None = typer.Option(None, "--ticker", "-t"),
    cik: str | None = typer.Option(None, "--cik"),
    accession: str | None = typer.Option(None, "--accession", "-a"),
    form: str = typer.Option("10-K", "--form", "-f"),
    force_refresh: bool = typer.Option(False, "--force-refresh"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    if not ticker and not cik and not accession:
        raise typer.BadParameter("Provide --ticker, --cik, or --accession")
    try:
        _validate_identifiers(ticker, cik)
    except ResolutionError as exc:
        raise typer.BadParameter(str(exc)) from exc

    request = CLIAskRequest(
        identifier=IssuerIdentifierInput(ticker=ticker, cik=cik, accession=accession),
        query=query,
        form_types=[form],
        force_refresh=force_refresh,
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
