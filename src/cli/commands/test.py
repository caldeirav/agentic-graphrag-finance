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
    macro_binding: bool = typer.Option(
        False,
        "--macro-binding",
        help="Run FinAgentBench macro_binding.jsonl slice (008); requires materialized snapshot",
    ),
    gold_path: bool = typer.Option(
        False,
        "--gold-path",
        help="Run gold-path navigation reachability slice (009)",
    ),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    if not ticker and not cik and not accession:
        raise typer.BadParameter("Provide --ticker, --cik, or --accession")

    if gold_path:
        from cli.gold_path_eval import run_gold_path_eval

        report = run_gold_path_eval()
        if as_json:
            typer.echo(json.dumps(report, indent=2))
        else:
            typer.echo(
                f"gold_path_reach={report['chunk_reach_rate']:.1%} "
                f"path_match={report['path_match_rate']:.1%} ({report['hits']}/{report['total']})"
            )
        if not report.get("passed"):
            raise typer.Exit(code=1)
        return

    if macro_binding:
        from cli.macro_binding_eval import run_macro_binding_eval

        report = run_macro_binding_eval(ticker=ticker or "AAPL")
        if as_json:
            typer.echo(json.dumps(report, indent=2))
        else:
            typer.echo(
                f"macro_binding_accuracy={report['macro_binding_accuracy']:.1%} "
                f"({report['hits']}/{report['total']})"
            )
            typer.echo(f"multi_filing_rate={report['multi_filing_rate']:.1%}")
        if not report.get("passed"):
            raise typer.Exit(code=1)
        return

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
