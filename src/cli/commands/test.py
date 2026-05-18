"""agent-query test subcommand."""

from __future__ import annotations

import json

import typer

from cli.pipeline import run_test_pipeline


def test_cmd(
    ticker: str | None = typer.Option(None, "--ticker", "-t"),
    cik: str | None = typer.Option(None, "--cik"),
    accession: str | None = typer.Option(None, "--accession", "-a"),
    form: str = typer.Option("10-K", "--form", "-f"),
    force_refresh: bool = typer.Option(False, "--force-refresh"),
    min_sections: int = typer.Option(1, "--min-sections"),
    min_chunk_tables: int = typer.Option(0, "--min-chunk-tables"),
    check_registry: bool = typer.Option(False, "--check-registry"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    if not ticker and not cik and not accession:
        raise typer.BadParameter("Provide --ticker, --cik, or --accession")

    result = run_test_pipeline(
        ticker=ticker,
        cik=cik,
        accession=accession,
        form_type=form,
        force_refresh=force_refresh,
        min_sections=min_sections,
        min_chunk_tables=min_chunk_tables,
        check_registry=check_registry,
    )
    if as_json:
        typer.echo(json.dumps(result, indent=2))
    else:
        status = "PASS" if result["passed"] else "FAIL"
        typer.echo(f"{status}: structural checks")
        for k, v in result.get("node_counts", {}).items():
            typer.echo(f"  {k}: {v}")
        for msg in result.get("messages", []):
            typer.echo(f"  ! {msg}")
    if not result["passed"]:
        raise typer.Exit(code=1)
